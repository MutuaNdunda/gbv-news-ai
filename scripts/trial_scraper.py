"""Collect a bounded, unlabelled trial sample from Kenyan news publishers."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import logging
import os
from pathlib import Path
import sys
import hashlib
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bs4 import BeautifulSoup

from database.repositories.articles import ArticleRepository
from database.repositories.collection_runs import CollectionRunRepository
from database.session import create_session_factory, load_environment
from scrapers import citizen, kenyans, nation, standard, star, taifaleo, tuko
from scrapers.wayback_discovery import ArchiveSource, Discovery, term_pattern
from scrapers.common import Client, discover, normalize_url
from storage import GCSStorage
from storage.logging import GCSRunLogHandler
from storage.persistence import CollectionPersistence, IndexingError


SOURCES = {
    module.SOURCE: module
    for module in (nation, citizen, standard, star, tuko, kenyans, taifaleo)
}
LOGGER = logging.getLogger(__name__)


def build_services():
    sessions = create_session_factory()
    articles = ArticleRepository(sessions)
    runs = CollectionRunRepository(sessions)
    return CollectionPersistence(GCSStorage(), articles), articles, runs


def candidates(publisher, client, max_pages=1):
    """Prefer configured RSS, then fall back to publisher listing pages."""
    if hasattr(publisher, "expanded_candidates"):
        yield from publisher.expanded_candidates(client, max_pages)
        return
    seen = set()
    for feed in publisher.FEEDS:
        response = client.fetch(feed, stage="LISTING")
        if response is None:
            continue
        soup = BeautifulSoup(response.content, "xml")
        for item in soup.find_all("item"):
            link = item.find("link")
            url = normalize_url(link.get_text(strip=True)) if link else ""
            if publisher.accepts(url) and url not in seen:
                seen.add(url)
                yield url, feed, "rss"
    for listing in publisher.LISTINGS:
        response = client.fetch(listing, stage="LISTING")
        if response is None:
            continue
        discover_links = getattr(publisher, "discover", None)
        links = (discover_links(response.content, response.url) if discover_links
                 else discover(response.content, response.url, publisher.accepts))
        for url in links:
            if url not in seen:
                seen.add(url)
                yield url, response.url, "archive_listing" if discover_links else "listing"


def raw_identity_url(publisher, url: str) -> str:
    try:
        return publisher.archive_parts(url)[1]
    except (AttributeError, TypeError, ValueError):
        return normalize_url(url)


def archive_capture_month(publisher, url: str) -> str | None:
    """Return YYYY-MM for a validated archive replay, if the source provides one."""
    try:
        timestamp = publisher.archive_parts(url)[0]
    except (AttributeError, TypeError, ValueError):
        return None
    return f"{timestamp[:4]}-{timestamp[4:6]}"


def live_candidates(publisher, client, max_pages, urls=None):
    if urls is not None:
        for url in dict.fromkeys(urls):
            if publisher.is_article(url):
                yield url, url, 'manual_live_url'
        return
    seen = set()
    for listing in publisher.LIVE_LISTINGS[:max_pages]:
        response = client.fetch(listing, stage='LISTING')
        if response is None:
            continue
        for url in discover(response.content, response.url, publisher.is_article):
            if url not in seen:
                seen.add(url)
                yield url, response.url, 'live_listing'


def run_trial_extraction(sources=None, limit=20, delay=2.0, max_pages=1,
                         run_name=None, services=None, input_urls=None, wayback=False,
                         wayback_urls=None, wayback_start=None, wayback_end=None, wayback_section=None,
                         publication_start=None, publication_end=None, method=None, terms=(),
                         selection='newest', max_records=10000, max_index_requests=20, max_attempts=None):
    method = method or ('wayback' if wayback else 'listing')
    wayback = method == 'wayback'
    if method not in ('wayback', 'live', 'listing'):
        raise ValueError('Unsupported collection method')
    if min(limit, max_pages, max_records, max_index_requests) < 1 or (max_attempts is not None and max_attempts < 1):
        raise ValueError('Collection bounds must be positive')
    if terms and not wayback:
        raise ValueError('URL keyword terms require Wayback discovery')
    publication_from = date.fromisoformat(publication_start) if publication_start else None
    publication_to = date.fromisoformat(publication_end) if publication_end else None
    if publication_from and publication_to and publication_from > publication_to:
        raise ValueError('Publication start must precede publication end')
    if wayback and input_urls is not None:
        raise ValueError('Explicit live collection and Wayback discovery cannot be combined')
    if wayback_urls and (not wayback or input_urls is not None
                        or not all(any(pub.is_article(url) or pub.accepts(url) for pub in SOURCES.values()) for url in wayback_urls)):
        if method != 'live':
            raise ValueError('Wayback URLs must be supported article URLs or dated replays')
    if input_urls is not None and (sources != ['nation'] or not input_urls
                                  or not all(nation.accepts(url) or nation.is_article(url) for url in input_urls)):
        raise ValueError('Explicit URL collection requires valid Nation article URLs')
    persistence, articles, runs = services or build_services()
    selected = list(sources or SOURCES)
    run_name = run_name or datetime.now(timezone.utc).strftime("trial-%Y%m%dT%H%M%S%fZ")
    config = {"kind": "trial", "sources": selected, "limit": limit,
              "delay": delay, "max_pages": max_pages}
    if max_attempts is not None:
        config['max_attempts'] = max_attempts
    if publication_start or publication_end:
        config['publication_window'] = {'start': publication_start, 'end': publication_end}
    if wayback:
        config['wayback'] = {'version': 'shared-waybackpy-v2', 'start': wayback_start,
                                   'end': wayback_end, 'section': wayback_section, 'url_count': len(wayback_urls or []),
                                   'urls_sha256': hashlib.sha256('\n'.join(wayback_urls or []).encode()).hexdigest()}
        config['wayback'].update(terms=list(terms), selection=selection, max_records=max_records,
                                max_index_requests=max_index_requests, max_attempts=max_attempts or limit * 5)
    elif method == 'live':
        config['method'] = 'live'
        config['input_sha256'] = hashlib.sha256('\n'.join(wayback_urls or []).encode()).hexdigest()
    if input_urls is not None:
        config.update(kind='explicit_urls', input_count=len(input_urls),
                      input_sha256=hashlib.sha256('\n'.join(input_urls).encode()).hexdigest())
    if "taifaleo" in selected and max_pages > 1 and method == 'listing':
        config["discovery_versions"] = {"taifaleo": "cdx-resume-v1"}
    if "nation" in selected and max_pages > 1 and method == 'listing':
        config.setdefault("discovery_versions", {})["nation"] = "archive-listings-v1"
    run_id = runs.resolve(run_name, config)
    prefix = f"runs/{run_name}"
    state = persistence.objects.read_json("runs", f"{prefix}/progress.json") or {
        "config": config,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "running",
        "sources": {name: {"attempted": 0, "saved": 0} for name in selected},
        "pending_index": [],
    }
    if state["config"] != config:
        raise ValueError("Resume configuration differs from saved run")
    state["status"] = "running"
    state.setdefault("pending_index", [])
    persistence.objects.write_json("runs", f"{prefix}/progress.json", state)
    for pending in list(state["pending_index"]):
        persistence.retry_index(pending, run_id)
        state["pending_index"].remove(pending)
        persistence.objects.write_json("runs", f"{prefix}/progress.json", state)
    urls, hashes = articles.existing_identities()
    total = 0
    try:
        for name in selected:
            publisher = SOURCES[name]
            discovery = None
            adapter = ArchiveSource(publisher)
            source_state = state['sources'][name]
            for counter in ('candidates_discovered', 'duplicates', 'extraction_successes',
                            'fetch_failed', 'parse_failed', 'storage_failed', 'raw_stored'):
                source_state.setdefault(counter, 0)
            if method == 'live':
                if not hasattr(publisher, 'parse_live') or not hasattr(publisher, 'LIVE_LISTINGS'):
                    source_state['stop_reason'] = 'unsupported_live_adapter'
                    LOGGER.warning('%s has no live adapter; skipping without method fallback', name)
                    continue
                publisher = SimpleNamespace(**vars(publisher))
                publisher.HOSTS = publisher.PUBLISHER_HOSTS
                publisher.accepts = publisher.is_article
                publisher.accepts_fetch = adapter.live_fetch
                publisher.parse = publisher.parse_live
            if input_urls is not None:
                publisher = SimpleNamespace(**vars(publisher))
                publisher.HOSTS = nation.HOSTS + nation.PUBLISHER_HOSTS
                publisher.accepts = lambda url: nation.accepts(url) or nation.is_article(url)
                publisher.accepts_fetch = publisher.accepts
                publisher.parse = lambda html, url: (nation.parse(html, url) if nation.accepts(url)
                                                     else nation.parse_live(html, url))
            client = Client(publisher.HOSTS, delay,
                            os.environ.get("SCRAPER_USER_AGENT", "GBVResearchBot/0.1"),
                            url_validator=(adapter.accepts_fetch if wayback
                                           else getattr(publisher, "accepts_fetch", None)))
            client.source = name
            saved = attempted = 0
            try:
                candidate_iterator = (iter((url, url, 'manual_url') for url in input_urls)
                                      if input_urls is not None else iter(candidates(publisher, client, max_pages)))
                if wayback:
                    if not hasattr(publisher, 'ARCHIVE_PREFIXES') or not hasattr(publisher, 'archive_parts'):
                        source_state['stop_reason'] = 'unsupported_archive_adapter'
                        LOGGER.warning('%s has no archive adapter; skipping without method fallback', name)
                        continue
                    if wayback_section and name == 'nation':
                        adapted = SimpleNamespace(**vars(publisher))
                        adapted.ARCHIVE_PREFIXES = ('https://nation.africa/kenya/' + wayback_section + '/',)
                        adapter = ArchiveSource(adapted)
                    supplied = ([url for url in wayback_urls if publisher.is_article(url) or publisher.accepts(url)]
                                if wayback_urls is not None else None)
                    discovery = Discovery(adapter, client, terms=terms, start=wayback_start, end=wayback_end,
                        selection=selection, max_records=max_records, max_requests=max_index_requests,
                        max_pages=max_pages, urls=supplied)
                    candidate_iterator = iter(discovery.candidates())
                elif method == 'live':
                    supplied = [url for url in wayback_urls if publisher.is_article(url)] if wayback_urls is not None else None
                    candidate_iterator = iter(live_candidates(publisher, client, max_pages, supplied))
                identities = set()
                for known in urls:
                    try:
                        identities.add(adapter.identity(known))
                    except (ValueError, AttributeError):
                        pass
                attempt_limit = max_attempts or limit * 5
                source_state['stop_reason'] = 'candidates_exhausted'
                while saved < limit and attempted < attempt_limit:
                    try:
                        url, discovery_url, discovery_method = next(candidate_iterator)
                    except StopIteration:
                        break
                    identity_url = raw_identity_url(publisher, url)
                    normalized_identity = adapter.identity(url) if wayback or method == 'live' else identity_url
                    source_state['candidates_discovered'] = source_state.get('candidates_discovered', 0) + 1
                    if identity_url in urls or url in urls or normalized_identity in identities:
                        state['sources'][name]['duplicates'] = state['sources'][name].get('duplicates', 0) + 1
                        continue
                    attempted += 1
                    state["sources"][name]["attempted"] += 1
                    response = client.fetch(url, stage="ARTICLE_FETCH")
                    if response is None or "html" not in response.headers.get("Content-Type", "").lower():
                        state['sources'][name]['fetch_failed'] = state['sources'][name].get('fetch_failed', 0) + 1
                        continue
                    if not publisher.accepts(response.url):
                        source_state['fetch_failed'] = source_state.get('fetch_failed', 0) + 1
                        continue
                    try:
                        raw = persistence.store_raw(
                            name, identity_url, response.content,
                            archive_capture_month(publisher, response.url),
                        )
                        source_state['raw_stored'] += 1
                    except Exception:
                        source_state['storage_failed'] = source_state.get('storage_failed', 0) + 1
                        LOGGER.exception("Raw GCS persistence failed for %s", url)
                        continue
                    try:
                        article = publisher.parse(response.content, response.url)
                    except (ValueError, TypeError, AttributeError):
                        article = None
                    if not article:
                        state['sources'][name]['parse_failed'] = state['sources'][name].get('parse_failed', 0) + 1
                        LOGGER.warning("No accessible article body: %s", url)
                        continue
                    source_state['extraction_successes'] = source_state.get('extraction_successes', 0) + 1
                    if publication_from or publication_to:
                        try:
                            published = datetime.fromisoformat(article.get('published_at', '').replace('Z', '+00:00')).date()
                        except (ValueError, TypeError, AttributeError):
                            field = 'publication_date_missing'
                            state['sources'][name][field] = state['sources'][name].get(field, 0) + 1
                            continue
                        if ((publication_from and published < publication_from)
                                or (publication_to and published > publication_to)):
                            field = 'outside_publication_window'
                            state['sources'][name][field] = state['sources'][name].get(field, 0) + 1
                            continue
                    if article["canonical_url"] in urls or (name, article["content_hash"]) in hashes:
                        state['sources'][name]['duplicates'] = state['sources'][name].get('duplicates', 0) + 1
                        LOGGER.info("Duplicate detected: %s", url)
                        continue
                    article.update(requested_url=url, discovery_url=discovery_url,
                                   discovery_method=discovery_method, http_status=response.status_code)
                    if terms:
                        article.update(discovery_terms=list(terms), candidate_sampling='url_keyword_enrichment')
                    if not article["published_at"]:
                        article["publication_date_needs_review"] = True
                    try:
                        created = persistence.persist_article(article, raw, run_id)
                    except IndexingError as exc:
                        source_state['storage_failed'] = source_state.get('storage_failed', 0) + 1
                        state["pending_index"].append(exc.pending)
                        persistence.objects.write_json("runs", f"{prefix}/progress.json", state)
                        raise
                    except Exception:
                        source_state['storage_failed'] += 1
                        LOGGER.exception('Normalized GCS persistence failed for %s', url)
                        continue
                    if not created:
                        source_state['duplicates'] = source_state.get('duplicates', 0) + 1
                        LOGGER.info("Existing extraction version resolved: %s", url)
                        continue
                    urls.update((identity_url, article["canonical_url"], article["url"]))
                    identities.add(normalized_identity)
                    hashes.add((name, article["content_hash"]))
                    saved += 1
                    total += 1
                    state["sources"][name]["saved"] += 1
                    state["updated_at"] = datetime.now(timezone.utc).isoformat()
                    persistence.objects.write_json("runs", f"{prefix}/progress.json", state)
                    LOGGER.info("Article stored: %s", url)
                if saved >= limit:
                    source_state['stop_reason'] = 'article_limit'
                elif attempted >= attempt_limit:
                    source_state['stop_reason'] = 'max_attempts'
            except IndexingError:
                source_state['stop_reason'] = 'storage_index_failed'
                LOGGER.warning('%s indexing failed after GCS persistence; pending recovery retained', name)
            finally:
                if discovery:
                    source_state['discovery'] = discovery.stats
                    if source_state.get('stop_reason') == 'candidates_exhausted':
                        source_state['stop_reason'] = discovery.stats['discovery_stop_reason']
                client.session.close()
            LOGGER.info("%s: stored %d trial articles (%d attempted)", name, saved, attempted)
            LOGGER.info('%s counters: %s', name, source_state)
            state['updated_at'] = datetime.now(timezone.utc).isoformat()
            persistence.objects.write_json('runs', f'{prefix}/progress.json', state)
        runs.set_status(run_id, "completed")
        state["status"] = "completed"
        if any(item.get('discovery', {}).get('index_failures') or item.get('storage_failed')
               or item.get('stop_reason', '').startswith('unsupported') for item in state['sources'].values()):
            state['status'] = 'finished_with_gaps'
            runs.set_status(run_id, 'finished_with_gaps')
    except BaseException:
        runs.set_status(run_id, "failed")
        state["status"] = "failed"
        raise
    finally:
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        persistence.objects.write_json("runs", f"{prefix}/progress.json", state)
        rows = ["source,attempted,saved"]
        rows.extend(
            f"{name},{state['sources'][name]['attempted']},{state['sources'][name]['saved']}"
            for name in selected
        )
        persistence.objects.write_bytes(
            "runs", f"{prefix}/trial_counts.csv", ("\n".join(rows) + "\n").encode(),
            "text/csv; charset=utf-8",
        )
        persistence.objects.write_json('runs', f'{prefix}/trial_report.json',
                                       {'status': state['status'], 'sources': state['sources']})
    LOGGER.info("Trial finished: %d new articles; status=%s. Manual quality/relevance review required.", total, state['status'])
    return total


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=SOURCES, action="append")
    parser.add_argument('--sources', choices=SOURCES, nargs='+', action='extend', help='Select one or multiple registered publishers')
    parser.add_argument("--limit", type=int, default=20,
                        help="Maximum new articles saved per selected publisher per invocation")
    parser.add_argument("--max-pages", type=int,
                        help="Maximum CDX pages per prefix, default 20 for Wayback; listing/live pages default 1")
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--run-name")
    parser.add_argument('--method', choices=['wayback', 'live', 'listing'], default='wayback',
                        help='Default: historical Wayback; live: publisher monitoring; listing: legacy archived listing collector')
    parser.add_argument('--wayback', dest='method', action='store_const', const='wayback', help='Compatibility alias for --method wayback')
    parser.add_argument('--url', action='append', help='Resolve a supplied live article URL to an archive; accept dated replays, or fetch live with --method live')
    parser.add_argument('--term', action='append', default=[], help='Literal case-insensitive OR match against original URL text, not article titles or bodies; repeatable')
    parser.add_argument('--from-date', help='Inclusive capture start YYYY-MM-DD, not article publication date')
    parser.add_argument('--to-date', help='Inclusive capture end YYYY-MM-DD, not article publication date')
    parser.add_argument('--selection', choices=['newest', 'oldest'], default='newest', help='One capture per article among bounded discovered records')
    parser.add_argument('--max-records', type=int, default=10000, help='Maximum CDX records per publisher, including duplicate captures')
    parser.add_argument('--max-index-requests', type=int, default=20, help='Maximum logical CDX requests per publisher; shared HTTP retries remain capped at three')
    parser.add_argument('--max-attempts', type=int, help='Maximum article retrieval attempts per publisher; default five times limit')
    parser.add_argument('--dry-run', action='store_true', help='Print plan offline, without HTTP, cloud credentials or database access')
    parser.add_argument('--wayback-start', help='Optional capture start date YYYYMMDD')
    parser.add_argument('--wayback-end', help='Optional capture end date YYYYMMDD')
    parser.add_argument('--wayback-section', choices=['news', 'counties', 'business', 'sports',
                        'life-and-style', 'health', 'weekly-review', 'blogs-opinion'],
                        help='Optional Nation section prefix; otherwise scans all Kenya URLs')
    parser.add_argument('--publication-start', help='Inclusive article publication date YYYY-MM-DD')
    parser.add_argument('--publication-end', help='Inclusive article publication date YYYY-MM-DD')
    args = parser.parse_args(argv)
    if args.max_pages is None:
        args.max_pages = 20 if args.method == 'wayback' else 1
    args.source = list(dict.fromkeys((args.source or []) + (args.sources or []))) or list(SOURCES)
    if min(args.limit, args.max_pages, args.max_records, args.max_index_requests) < 1 or (args.max_attempts is not None and args.max_attempts < 1) or not 1.5 <= args.delay < float("inf"):
        parser.error("limit and max-pages must be positive; delay must be finite and at least 1.5 seconds")
    try:
        term_pattern(args.term)
        for name, legacy in [('from_date', 'wayback_start'), ('to_date', 'wayback_end')]:
            value = getattr(args, name)
            if value:
                parsed = date.fromisoformat(value)
                if value != parsed.isoformat():
                    raise ValueError('Use ISO YYYY-MM-DD dates')
                encoded = parsed.strftime('%Y%m%d')
                if getattr(args, legacy) and getattr(args, legacy) != encoded:
                    parser.error('Conflicting capture date aliases')
                setattr(args, legacy, encoded)
    except ValueError:
        parser.error('Capture dates must be valid YYYY-MM-DD and terms must not be blank')
    if (args.term or args.wayback_start or args.wayback_end or args.wayback_section) and args.method != 'wayback':
        parser.error('Terms and capture bounds require Wayback collection')
    for value in (args.wayback_start, args.wayback_end):
        if value:
            try:
                if len(value) != 8 or not value.isdigit():
                    raise ValueError()
                datetime.strptime(value, '%Y%m%d')
            except ValueError:
                parser.error('Capture bounds must be valid YYYYMMDD dates')
    if args.wayback_start and args.wayback_end and args.wayback_start > args.wayback_end:
        parser.error('Capture start must precede capture end')
    try:
        for value in (args.publication_start, args.publication_end):
            if value:
                if date.fromisoformat(value).isoformat() != value:
                    raise ValueError('Use ISO YYYY-MM-DD dates')
        if args.publication_start and args.publication_end and args.publication_start > args.publication_end:
            raise ValueError()
    except ValueError:
        parser.error('Publication bounds must be valid YYYY-MM-DD dates, with start before end')
    if args.wayback_section and 'nation' not in args.source:
        parser.error('--wayback-section is a legacy Nation-only scope option')
    if args.url and not all(any(SOURCES[name].is_article(url) or (args.method == 'wayback' and SOURCES[name].accepts(url))
                              for name in args.source) for url in args.url):
        parser.error('--url must match an article adapter for a selected publisher; login routes are rejected')
    return args


def main(argv=None):
    args = parse_args(argv)
    if args.dry_run:
        import json
        print(json.dumps(dict(sources=args.source, method=args.method, terms=args.term,
            url_regex=term_pattern(args.term), capture_from=args.wayback_start, capture_to=args.wayback_end,
            publication_from=args.publication_start, publication_to=args.publication_end, selection=args.selection,
            limit_per_publisher=args.limit, max_records_per_publisher=args.max_records,
            max_index_requests_per_publisher=args.max_index_requests, max_pages_per_prefix=args.max_pages,
            max_attempts_per_publisher=args.max_attempts or args.limit * 5, delay=args.delay,
            prefixes={name: list(SOURCES[name].ARCHIVE_PREFIXES) for name in args.source}), indent=2))
        return
    load_environment()
    run_name = args.run_name or datetime.now(timezone.utc).strftime("trial-%Y%m%dT%H%M%S%fZ")
    services = build_services()
    log_handler = GCSRunLogHandler(
        services[0].objects, f"runs/{run_name}/collection.log"
    )
    log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(), log_handler])
    with services[2].lock(run_name):
        run_trial_extraction(
            args.source, args.limit, args.delay, args.max_pages, run_name, services,
            method=args.method, wayback_urls=args.url, terms=args.term, selection=args.selection,
            max_records=args.max_records, max_index_requests=args.max_index_requests, max_attempts=args.max_attempts,
            wayback_start=args.wayback_start, wayback_end=args.wayback_end, wayback_section=args.wayback_section,
            publication_start=args.publication_start, publication_end=args.publication_end
        )


if __name__ == "__main__":
    main()
