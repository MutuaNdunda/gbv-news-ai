"""Collect a bounded, unlabelled trial sample from Kenyan news publishers."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bs4 import BeautifulSoup

from database.repositories.articles import ArticleRepository
from database.repositories.collection_runs import CollectionRunRepository
from database.session import create_session_factory, load_environment
from scrapers import citizen, kenyans, nation, standard, star, tuko
from scrapers.common import Client, discover, normalize_url
from storage import GCSStorage
from storage.logging import GCSRunLogHandler
from storage.persistence import CollectionPersistence, IndexingError


SOURCES = {
    module.SOURCE: module
    for module in (nation, citizen, standard, star, tuko, kenyans)
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
    except (AttributeError, ValueError):
        return normalize_url(url)


def archive_capture_month(publisher, url: str) -> str | None:
    """Return YYYY-MM for a validated archive replay, if the source provides one."""
    try:
        timestamp = publisher.archive_parts(url)[0]
    except (AttributeError, TypeError, ValueError):
        return None
    return f"{timestamp[:4]}-{timestamp[4:6]}"


def run_trial_extraction(sources=None, limit=20, delay=2.0, max_pages=1,
                         run_name=None, services=None):
    persistence, articles, runs = services or build_services()
    selected = list(sources or SOURCES)
    run_name = run_name or datetime.now(timezone.utc).strftime("trial-%Y%m%dT%H%M%S%fZ")
    config = {"kind": "trial", "sources": selected, "limit": limit,
              "delay": delay, "max_pages": max_pages}
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
            client = Client(publisher.HOSTS, delay,
                            os.environ.get("SCRAPER_USER_AGENT", "GBVResearchBot/0.1"),
                            url_validator=getattr(publisher, "accepts_fetch", None))
            client.source = name
            saved = attempted = 0
            try:
                for url, discovery_url, method in candidates(publisher, client, max_pages):
                    identity_url = raw_identity_url(publisher, url)
                    if saved >= limit or attempted >= limit * 5:
                        break
                    if identity_url in urls or url in urls:
                        continue
                    attempted += 1
                    state["sources"][name]["attempted"] += 1
                    response = client.fetch(url, stage="ARTICLE_FETCH")
                    if response is None or "html" not in response.headers.get("Content-Type", "").lower():
                        continue
                    if not publisher.accepts(response.url):
                        continue
                    try:
                        raw = persistence.store_raw(
                            name, identity_url, response.content,
                            archive_capture_month(publisher, response.url),
                        )
                    except Exception:
                        LOGGER.exception("Raw GCS persistence failed for %s", url)
                        continue
                    try:
                        article = publisher.parse(response.content, response.url)
                    except (ValueError, TypeError, AttributeError):
                        article = None
                    if not article:
                        LOGGER.warning("No accessible article body: %s", url)
                        continue
                    if article["canonical_url"] in urls or (name, article["content_hash"]) in hashes:
                        LOGGER.info("Duplicate detected: %s", url)
                        continue
                    article.update(requested_url=url, discovery_url=discovery_url,
                                   discovery_method=method, http_status=response.status_code)
                    if not article["published_at"]:
                        article["publication_date_needs_review"] = True
                    try:
                        created = persistence.persist_article(article, raw, run_id)
                    except IndexingError as exc:
                        state["pending_index"].append(exc.pending)
                        persistence.objects.write_json("runs", f"{prefix}/progress.json", state)
                        raise
                    if not created:
                        LOGGER.info("Existing extraction version resolved: %s", url)
                        continue
                    urls.update((identity_url, article["canonical_url"], article["url"]))
                    hashes.add((name, article["content_hash"]))
                    saved += 1
                    total += 1
                    state["sources"][name]["saved"] += 1
                    state["updated_at"] = datetime.now(timezone.utc).isoformat()
                    persistence.objects.write_json("runs", f"{prefix}/progress.json", state)
                    LOGGER.info("Article stored: %s", url)
            finally:
                client.session.close()
            LOGGER.info("%s: stored %d trial articles (%d attempted)", name, saved, attempted)
        runs.set_status(run_id, "completed")
        state["status"] = "completed"
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
    LOGGER.info("Trial complete: %d new articles. Manual quality/relevance review required.", total)
    return total


def main():
    load_environment()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=SOURCES, action="append")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--run-name")
    args = parser.parse_args()
    if args.limit < 1 or args.max_pages < 1 or not 1.5 <= args.delay < float("inf"):
        parser.error("limit and max-pages must be positive; delay must be finite and at least 1.5 seconds")
    run_name = args.run_name or datetime.now(timezone.utc).strftime("trial-%Y%m%dT%H%M%S%fZ")
    services = build_services()
    log_handler = GCSRunLogHandler(
        services[0].objects, f"runs/{run_name}/collection.log"
    )
    log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(), log_handler])
    with services[2].lock(run_name):
        run_trial_extraction(
            args.source, args.limit, args.delay, args.max_pages, run_name, services
        )


if __name__ == "__main__":
    main()
