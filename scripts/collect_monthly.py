"""Collect broad archived reporting and persist it to GCS and Supabase."""

from __future__ import annotations

import argparse
import calendar
import csv
from datetime import date, datetime, timezone
import hashlib
from io import StringIO
import json
import logging
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlencode, unquote_plus, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scrapers.common import Client, normalize_url
from scripts.trial_scraper import SOURCES, build_services
from database.repositories.collection_run_scans import CollectionRunScanRepository
from storage.logging import GCSRunLogHandler
from storage.persistence import IndexingError


LOG = logging.getLogger(__name__)
CDX = "https://web.archive.org/cdx/search/cdx"


def months_descending(start, end):
    first = datetime.strptime(start, "%Y-%m").date()
    last = datetime.strptime(end, "%Y-%m").date()
    if first > last:
        raise ValueError("start month must not follow end month")
    result = []
    cursor = last
    while cursor >= first:
        result.append(cursor.strftime("%Y-%m"))
        cursor = date(cursor.year - (cursor.month == 1),
                      12 if cursor.month == 1 else cursor.month - 1, 1)
    return result


def publication_month(value):
    """Use the stated publication calendar date; never archive or scrape time."""
    if not isinstance(value, str) or not re.match(r"^\d{4}-\d{2}-\d{2}", value):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m")
    except ValueError:
        return None


def index_url(publisher, month, resume=None):
    year, number = map(int, month.split("-"))
    default_scope = (publisher.PUBLISHER_HOSTS[0].removeprefix("www."), "domain")
    scope = getattr(publisher, "CDX_INDEX_SCOPE", default_scope)
    if (not isinstance(scope, tuple) or len(scope) != 2
            or not all(isinstance(value, str) for value in scope)):
        scope = default_scope
    target, match_type = scope
    query = [("url", target), ("matchType", match_type),
             ("from", f"{year}{number:02d}01"),
             ("to", f"{year}{number:02d}{calendar.monthrange(year, number)[1]}"),
             ("output", "json"), ("fl", "timestamp,original"),
             ("filter", "statuscode:200"), ("filter", "mimetype:text/html"),
             ("collapse", "urlkey"), ("limit", "1000"),
             ("showResumeKey", "true")]
    if resume:
        query.append(("resumeKey", unquote_plus(resume)))
    return CDX + "?" + urlencode(query)


def parse_index(payload):
    if not isinstance(payload, list):
        raise ValueError("Expected CDX JSON array")
    if not payload:
        return [], None
    if payload[0] != ["timestamp", "original"]:
        raise ValueError("Unexpected CDX columns")
    records, resume = [], None
    for i, row in enumerate(payload[1:], 1):
        if row == []:
            if i + 1 < len(payload) and len(payload[i + 1]) == 1:
                resume = payload[i + 1][0]
                if not isinstance(resume, str):
                    raise ValueError("Invalid resume key")
                break
            raise ValueError("Invalid CDX continuation")
        if not isinstance(row, list) or len(row) != 2 or not all(isinstance(x, str) for x in row):
            raise ValueError("Invalid CDX record")
        if not re.fullmatch(r"\d{14}", row[0]):
            raise ValueError("Invalid capture timestamp")
        records.append(tuple(row))
    return records, resume


def initial_state(config, months):
    state = {"config": config, "months": months, "saved": {}, "scans": {},
             "started_at": datetime.now(timezone.utc).isoformat(), "status": "running"}
    state["pending_index"] = []
    for month in months:
        for source in config["sources"]:
            key = f"{source}/{month}"
            state["saved"][key] = 0
            state["scans"][key] = {
                "status": "pending", "index_pages": 0, "candidates": 0,
                "attempted": 0, "saved": 0, "duplicates": 0, "failed": 0,
                "outside_period": 0, "unknown_date": 0,
            }
    return state


def report(run_name, run_id, state, objects, articles, scans):
    totals = articles.counts(state["config"]["sources"], state["months"])
    saved = articles.counts(state["config"]["sources"], state["months"], run_id)
    rows = []
    for month in state["months"]:
        for source in state["config"]["sources"]:
            key = f"{source}/{month}"
            state["saved"][key] = saved[(source, month)]
            scans.update(run_id, source, month, state["scans"][key])
            rows.append({"source": source, "publication_month": month,
                         "new_articles_this_run": saved[(source, month)],
                         "total_stored_articles": totals[(source, month)],
                         "same_month_capture_scan": state["scans"][key]["status"],
                         "kenya_relevance": "needs_review"})
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    prefix = f"runs/{run_name}"
    objects.write_bytes("runs", f"{prefix}/monthly_counts.csv",
                        stream.getvalue().encode(), "text/csv; charset=utf-8")
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    objects.write_json("runs", f"{prefix}/progress.json", state)
    return rows


def run(config, run_name, services=None):
    supplied = services or build_services()
    persistence, articles, runs = supplied[:3]
    scans = supplied[3] if len(supplied) > 3 else CollectionRunScanRepository(articles.sessions)
    objects = persistence.objects
    months = months_descending(config["start_month"], config["end_month"])
    run_id = runs.resolve(run_name, config)
    progress_name = f"runs/{run_name}/progress.json"
    state = objects.read_json("runs", progress_name)
    if state is not None and state["config"] != config:
        raise ValueError("Resume configuration differs from saved run")
    state = state or initial_state(config, months)
    state["status"] = "running"
    state.setdefault("pending_index", [])
    for pending in list(state["pending_index"]):
        persistence.retry_index(pending, run_id)
        state["pending_index"].remove(pending)
        objects.write_json("runs", progress_name, state)
    urls, hashes = articles.existing_identities()
    failures = 0
    index_client = Client(("web.archive.org",), config["delay"],
                          os.environ.get("SCRAPER_USER_AGENT", "GBVResearchBot/0.1"),
                          url_validator=lambda url: urlsplit(url).path == "/cdx/search/cdx",
                          request_stage="cdx_index")
    article_client = Client(
        ("web.archive.org",), config["delay"], index_client.user_agent,
        request_stage="wayback_replay",
    )
    report(run_name, run_id, state, objects, articles, scans)
    try:
        for month in months:
            for name in config["sources"]:
                key = f"{name}/{month}"
                scan = state["scans"][key]
                if scan["status"] == "index_exhausted":
                    continue
                publisher = SOURCES[name]
                article_client.url_validator = publisher.accepts
                scan["status"] = "running"
                scans.update(run_id, name, month, scan)
                resume = None
                seen_tokens, seen_originals = set(), set()
                attempts_this_scan = pages_this_scan = 0
                LOG.info("Starting %s capture month %s", name, month)
                while True:
                    query = index_url(publisher, month, resume)
                    digest = hashlib.sha256(query.encode()).hexdigest()
                    cache_name = f"runs/{run_name}/cdx-cache/{digest}.cdx.json"
                    index_client.last_request = max(index_client.last_request, article_client.last_request)
                    payload = objects.read_json("runs", cache_name)
                    if payload is None:
                        response = index_client.fetch(query)
                        if response is None:
                            scan["failed"] += 1
                            scan.update(status="index_failed", error=index_client.last_failure)
                            LOG.warning(
                                "%s %s CDX index unavailable: %s",
                                name, month, index_client.last_failure,
                            )
                            failures += 1
                            break
                        try:
                            payload = response.json()
                            parse_index(payload)
                        except (ValueError, TypeError):
                            scan["failed"] += 1
                            scan.update(status="index_failed", error={"kind": "invalid_index_response"})
                            failures += 1
                            break
                        objects.write_json("runs", cache_name, payload, create_only=True)
                    records, next_resume = parse_index(payload)
                    failures = 0
                    pages_this_scan += 1
                    scan["index_pages"] += 1
                    for timestamp, original in records:
                        original = normalize_url(original)
                        if not publisher.is_article(original) or original in seen_originals:
                            continue
                        seen_originals.add(original)
                        scan["candidates"] += 1
                        if original in urls:
                            scan["duplicates"] += 1
                            continue
                        if config["max_fetches_per_month"] and attempts_this_scan >= config["max_fetches_per_month"]:
                            scan["status"] = "fetch_limit"
                            break
                        replay = f"https://web.archive.org/web/{timestamp}/{original}"
                        attempts_this_scan += 1
                        scan["attempted"] += 1
                        article_client.last_request = max(article_client.last_request, index_client.last_request)
                        response = article_client.fetch(replay)
                        if response is None or "html" not in response.headers.get("Content-Type", "").lower():
                            scan["failed"] += 1
                            LOG.warning("Article fetch failed: %s reason=%s", replay, article_client.last_failure)
                            continue
                        try:
                            raw = persistence.store_raw(name, original, response.content, month)
                        except Exception:
                            scan["failed"] += 1
                            LOG.exception("Raw GCS persistence failed: %s", replay)
                            continue
                        try:
                            article = publisher.parse(response.content, response.url)
                        except (ValueError, TypeError, AttributeError):
                            article = None
                        if not article:
                            scan["failed"] += 1
                            LOG.warning("No accessible parsed body: %s", replay)
                            continue
                        published = publication_month(article.get("published_at"))
                        if published is None:
                            scan["unknown_date"] += 1
                            LOG.warning("Unknown publication date: %s", replay)
                            continue
                        if published not in months:
                            scan["outside_period"] += 1
                            continue
                        if article["canonical_url"] in urls or (name, article["content_hash"]) in hashes:
                            scan["duplicates"] += 1
                            continue
                        article.update(requested_url=replay, discovery_url=query,
                                       discovery_method="wayback_cdx", http_status=response.status_code,
                                       publication_month=published, collection_run=run_name,
                                       discovery_capture_month=month)
                        try:
                            created = persistence.persist_article(article, raw, run_id)
                        except IndexingError as exc:
                            state["pending_index"].append(exc.pending)
                            objects.write_json("runs", progress_name, state)
                            raise
                        if not created:
                            scan["duplicates"] += 1
                            continue
                        urls.update((original, article["url"], article["canonical_url"]))
                        hashes.add((name, article["content_hash"]))
                        scan["saved"] += 1
                        state["saved"][f"{name}/{published}"] += 1
                        LOG.info("Stored %s publication_month=%s capture_month=%s url=%s",
                                 name, published, month, article["canonical_url"])
                        report(run_name, run_id, state, objects, articles, scans)
                    if scan["status"] == "fetch_limit":
                        break
                    if not next_resume:
                        scan["status"] = "index_exhausted_with_gaps" if scan["failed"] or scan["unknown_date"] else "index_exhausted"
                        break
                    if config["max_index_pages"] and pages_this_scan >= config["max_index_pages"]:
                        scan["status"] = "index_page_limit"
                        break
                    if next_resume in seen_tokens:
                        scan["failed"] += 1
                        scan.update(status="index_failed", error={"kind": "repeated_resume_key"})
                        failures += 1
                        break
                    seen_tokens.add(next_resume)
                    resume = next_resume
                LOG.info("%s %s: %s; saved=%d failures=%d", name, month,
                         scan["status"], scan["saved"], scan["failed"])
                report(run_name, run_id, state, objects, articles, scans)
                if failures >= 3:
                    state["status"] = "paused_index_unavailable"
                    LOG.error("Three index failures in succession; leaving remaining scans pending")
                    return state
        state["status"] = "finished_with_gaps" if any(
            scan["status"] != "index_exhausted" or scan["failed"] or scan["unknown_date"]
            for scan in state["scans"].values()) else "index_scans_finished"
        return state
    except KeyboardInterrupt:
        state["status"] = "interrupted"
        return state
    except BaseException:
        state["status"] = "failed"
        raise
    finally:
        rows = report(run_name, run_id, state, objects, articles, scans)
        runs.set_status(run_id, state["status"])
        index_client.session.close()
        article_client.session.close()
        for row in rows:
            LOG.info("MONTHLY %s %s new=%s total=%s scan=%s", row["source"],
                     row["publication_month"], row["new_articles_this_run"],
                     row["total_stored_articles"], row["same_month_capture_scan"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-month", default="2026-01")
    parser.add_argument("--end-month", default="2026-08")
    parser.add_argument("--source", action="append", choices=SOURCES)
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--max-index-pages", type=int, default=0)
    parser.add_argument("--max-fetches-per-month", type=int, default=0)
    parser.add_argument("--run-name")
    args = parser.parse_args()
    try:
        months_descending(args.start_month, args.end_month)
    except ValueError as exc:
        parser.error(str(exc))
    if not 1.5 <= args.delay < float("inf") or args.max_index_pages < 0 or args.max_fetches_per_month < 0:
        parser.error("delay must be finite and >=1.5; limits must be nonnegative")
    config = {"kind": "monthly", "start_month": args.start_month,
              "end_month": args.end_month,
              "sources": list(dict.fromkeys(args.source or SOURCES)),
              "delay": args.delay, "max_index_pages": args.max_index_pages,
              "max_fetches_per_month": args.max_fetches_per_month}
    run_name = args.run_name or datetime.now(timezone.utc).strftime("monthly-%Y%m%dT%H%M%S%fZ")
    services = build_services()
    log_handler = GCSRunLogHandler(services[0].objects, f"runs/{run_name}/collection.log")
    log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(), log_handler])
    LOG.info("Run name: %s", run_name)
    with services[2].lock(run_name):
        result = run(config, run_name, services)
    LOG.info("Run status: %s", result["status"])
    return 0 if result["status"] == "index_scans_finished" else 2


if __name__ == "__main__":
    raise SystemExit(main())
