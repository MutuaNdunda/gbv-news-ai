#!/usr/bin/env python3
"""
Wayback Machine trial scraper for Kenyan news sources.

Discovers archived article URLs from the Internet Archive CDX API for a fixed
set of publishers, fetches the archived snapshots, extracts a normalized
article record, and writes:

    data/trials/raw/<source>/<hash>.html        (raw snapshot)
    data/trials/processed/<source>.jsonl        (normalized records)
    data/trials/processed/<source>.manifest.json

Trial / exploratory collector only, per AGENTS.md:
  * trial data lives under data/trials/ and must not be committed
  * scrapers do not decide GBV relevance
  * provenance (original URL, timestamp, discovery method) is preserved
  * polite delays + retries, no auth/paywall bypass

Usage examples
--------------
    python scrapers/wayback.py --months 3
    python scrapers/wayback.py --sources nation citizen --months 1 -v
    python scrapers/wayback.py --end 2026-09-30 --months 2 --max-articles 100
    python scrapers/wayback.py --sources taifaleo --all-dates --limit 500 --max-articles 2 --max-fetches 2

Taifa Leo uses its publisher-specific parser and the robots-aware shared HTTP
client. The six older source paths retain the generic experimental parser.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scrapers import taifaleo
from scrapers.common import Client

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

SOURCES: dict[str, str] = {
    "nation":   "nation.africa",
    "citizen":  "citizen.digital",
    "kenyans":  "kenyans.co.ke",
    "standard": "standardmedia.co.ke",
    "star":     "the-star.co.ke",
    "tuko":     "tuko.co.ke",
    "taifaleo": "taifaleo.nation.co.ke",
}

CDX_ENDPOINT = "https://web.archive.org/cdx/search/cdx"
WAYBACK_WEB = "https://web.archive.org/web/"

USER_AGENT = os.environ.get("SCRAPER_USER_AGENT", "GBVResearchBot/0.1")
REQUEST_TIMEOUT = 30
RETRIES = 3
DELAY_SECONDS = 1.5  # polite pacing between snapshot fetches
PARSER_VERSION = "wayback-0.1.0"

# URL shapes that typically indicate an article page (used as a coarse filter).
ARTICLE_URL_HINTS = re.compile(
    r"(/article/|/news/|/story/|/read/|/society/|/counties/|/crime/|"
    r"/politics/|/health/|/education/|/courts/|/national/|/world/|"
    r"/opinion/|/entertainment/|/metro/|/\d{4}/\d{2}/|/\d{6,})",
    re.IGNORECASE,
)

# URL shapes that are never articles.
SKIP_URL_HINTS = re.compile(
    r"(/tag/|/tags/|/category/|/categories/|/author/|/authors/|/page/|"
    r"/search|/video/|/videos/|/photo/|/photos/|/gallery/|/feed|/rss|"
    r"/sitemap|/about|/contact|/privacy|/terms|"
    r"\.(jpg|jpeg|png|gif|webp|svg|css|js|pdf|xml|json|mp4|mp3)$)",
    re.IGNORECASE,
)

LOG = logging.getLogger("wayback")


# --------------------------------------------------------------------------- #
# Normalized record (AGENTS.md §8)
# --------------------------------------------------------------------------- #

@dataclass
class Article:
    source: str
    url: str
    canonical_url: str
    title: str
    author: str
    published_at: str
    article_text: str
    language: str
    scraped_at: str
    section: str = ""
    content_hash: str = ""
    parser_version: str = PARSER_VERSION
    discovery_method: str = "wayback_cdx"
    http_status: int = 0
    wayback_timestamp: str = ""


# --------------------------------------------------------------------------- #
# HTTP helpers
# --------------------------------------------------------------------------- #

def http_get(url: str, *, params=None, session: requests.Session | None = None,
             client: Client | None = None):
    """GET with simple retries/backoff. Returns Response or None."""
    if client is not None:
        requested = requests.Request("GET", url, params=params).prepare().url
        stage = "CDX_INDEX" if url == CDX_ENDPOINT else "ARCHIVE_REPLAY"
        return client.fetch(requested, stage=stage)
    sess = session or requests
    last_err: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        try:
            r = sess.get(
                url,
                params=params,
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": USER_AGENT},
            )
            if r.status_code in (429, 500, 502, 503, 504):
                wait = DELAY_SECONDS * (2 ** attempt)
                LOG.warning("HTTP %s from %s; sleeping %.1fs",
                            r.status_code, url, wait)
                time.sleep(wait)
                continue
            return r
        except requests.RequestException as e:
            last_err = e
            wait = DELAY_SECONDS * (2 ** attempt)
            LOG.warning("request error (%s); retry in %.1fs", e, wait)
            time.sleep(wait)
    if last_err is not None:
        LOG.error("giving up on %s: %s", url, last_err)
    return None


# --------------------------------------------------------------------------- #
# URL utilities
# --------------------------------------------------------------------------- #

def canonicalize(url: str) -> str:
    """Lowercase host, strip www, drop query/fragment, normalize trailing slash."""
    try:
        p = urlparse(url)
    except Exception:
        return url
    netloc = p.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = p.path.rstrip("/") or "/"
    return urlunparse(("https", netloc, path, "", "", ""))


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def looks_like_article(url: str) -> bool:
    if SKIP_URL_HINTS.search(url):
        return False
    return bool(ARTICLE_URL_HINTS.search(url))


# --------------------------------------------------------------------------- #
# CDX discovery
# --------------------------------------------------------------------------- #

def cdx_params(domain, from_date, to_date, limit):
    params = {
        "url": f"{domain}/*", "output": "json",
        "fl": "timestamp,original,statuscode,mimetype",
        "filter": ["statuscode:200", "mimetype:text/html"],
        "collapse": "urlkey", "limit": str(limit),
    }
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date
    return params


def fetch_cdx(domain: str, from_date: str | None, to_date: str | None,
              limit: int, session: requests.Session,
              client: Client | None = None) -> list[dict]:
    """
    Query the Internet Archive CDX API for archived HTML pages on `domain`
    between `from_date` and `to_date` (both YYYYMMDD).
    """
    params = cdx_params(domain, from_date, to_date, limit)
    r = http_get(CDX_ENDPOINT, params=params, session=session, client=client)
    if r is None or r.status_code != 200:
        LOG.error("CDX query failed for %s (status=%s)",
                  domain, getattr(r, "status_code", "?"))
        if client is not None:
            raise RuntimeError("Taifa Leo CDX discovery failed; coverage is unknown")
        return []
    try:
        rows = r.json()
    except ValueError:
        LOG.error("CDX returned non-JSON for %s", domain)
        if client is not None:
            raise ValueError("Taifa Leo CDX returned invalid JSON")
        return []
    if client is not None:
        taifaleo.cdx_records(rows)
    if not rows:
        return []
    header, *data = rows
    return [dict(zip(header, row)) for row in data]


# --------------------------------------------------------------------------- #
# Article extraction
# --------------------------------------------------------------------------- #

def _meta(soup: BeautifulSoup, *names: str) -> str:
    for n in names:
        tag = soup.find("meta", attrs={"property": n}) or \
              soup.find("meta", attrs={"name": n})
        if tag and tag.get("content"):
            return tag["content"].strip()
    return ""


def _extract_body(soup: BeautifulSoup) -> str:
    candidates = [
        soup.find("article"),
        soup.find("div", attrs={"itemprop": "articleBody"}),
        soup.find("div", class_=re.compile(
            r"(article|story|post|entry)[-_]?(body|content|text)", re.I)),
    ]
    for c in candidates:
        if not c:
            continue
        paras = [p.get_text(" ", strip=True) for p in c.find_all("p")]
        text = "\n\n".join(p for p in paras if p)
        if len(text) > 200:
            return text

    # Fallback: all reasonably sized <p> tags
    paras = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    return "\n\n".join(p for p in paras if len(p) > 30)


def extract_article(html_bytes: bytes, source: str, original_url: str,
                    wayback_timestamp: str, http_status: int) -> Article:
    soup = BeautifulSoup(html_bytes, "lxml")

    title = (_meta(soup, "og:title", "twitter:title")
             or (soup.title.get_text(strip=True) if soup.title else ""))
    author = _meta(soup, "article:author", "author", "og:article:author")
    published = _meta(soup, "article:published_time",
                      "og:article:published_time", "pubdate", "date")
    section = _meta(soup, "article:section", "og:article:section")
    lang = _meta(soup, "og:locale", "language") or ""

    canon = ""
    link = soup.find("link", rel="canonical")
    if link and link.get("href"):
        canon = link["href"].strip()
    if not canon:
        canon = _meta(soup, "og:url") or original_url

    body = _extract_body(soup)

    return Article(
        source=source,
        url=original_url,
        canonical_url=canonicalize(canon),
        title=title,
        author=author,
        published_at=published,
        article_text=body,
        language=lang,
        scraped_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        section=section,
        content_hash=content_hash(body) if body else "",
        http_status=http_status,
        wayback_timestamp=wayback_timestamp,
    )


# --------------------------------------------------------------------------- #
# Per-source pipeline
# --------------------------------------------------------------------------- #

def _load_existing(jsonl_path: Path) -> tuple[set[str], set[str]]:
    hashes: set[str] = set()
    urls: set[str] = set()
    if not jsonl_path.exists():
        return hashes, urls
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("content_hash"):
                hashes.add(rec["content_hash"])
            if rec.get("canonical_url"):
                urls.add(rec["canonical_url"])
    return hashes, urls


def process_source(*, source: str, domain: str, from_date: str | None, to_date: str | None,
                   raw_root: Path, processed_root: Path,
                   cdx_limit: int, max_articles: int,
                   session: requests.Session, max_fetches: int = 0,
                   client: Client | None = None) -> dict:
    window = f"{from_date}..{to_date}" if from_date or to_date else "all capture dates"
    LOG.info("[%s] querying CDX %s (domain=%s)", source, window, domain)
    rows = fetch_cdx(domain, from_date, to_date, cdx_limit, session, client)
    LOG.info("[%s] CDX returned %d candidate rows", source, len(rows))

    src_raw_dir = raw_root / source
    src_raw_dir.mkdir(parents=True, exist_ok=True)
    processed_root.mkdir(parents=True, exist_ok=True)
    jsonl_path = processed_root / f"{source}.jsonl"
    manifest_path = processed_root / f"{source}.manifest.json"

    seen_hashes, seen_urls = _load_existing(jsonl_path)

    counters = {
        "source": source,
        "domain": domain,
        "from": from_date,
        "to": to_date,
        "cdx_rows": len(rows),
        "candidates_considered": 0,
        "snapshots_fetched": 0,
        "snapshots_reused": 0,
        "articles_written": 0,
        "skipped_short": 0,
        "skipped_duplicate": 0,
        "fetch_failed": 0,
        "parse_failed": 0,
        "fetch_attempts": 0,
        "stop_reason": "index_batch_exhausted",
        "cdx_limit": cdx_limit,
    }

    for row in rows:
        if counters["articles_written"] >= max_articles:
            counters["stop_reason"] = "article_limit"
            break
        original = (row.get("original") or "").strip()
        timestamp = (row.get("timestamp") or "").strip()
        if not original or not timestamp:
            continue
        if not (taifaleo.is_article(original) if source == "taifaleo" else looks_like_article(original)):
            continue

        canon = canonicalize(original)
        if canon in seen_urls:
            continue

        counters["candidates_considered"] += 1
        snap_url = f"{WAYBACK_WEB}{timestamp}id_/{original}"
        raw_name = hashlib.sha1(snap_url.encode("utf-8")).hexdigest()[:16] + ".html"
        raw_path = src_raw_dir / raw_name
        metadata_path = raw_path.with_suffix(".meta.json")
        actual_archive_url = snap_url

        if raw_path.exists() and (source != "taifaleo" or metadata_path.exists()):
            html_bytes = raw_path.read_bytes()
            http_status = 200
            if source == "taifaleo":
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                actual_archive_url = metadata["archive_url"]
                http_status = metadata["http_status"]
                if not taifaleo.accepts(actual_archive_url):
                    counters["parse_failed"] += 1
                    continue
            counters["snapshots_reused"] += 1
        else:
            if max_fetches and counters["fetch_attempts"] >= max_fetches:
                counters["stop_reason"] = "fetch_limit"
                break
            counters["fetch_attempts"] += 1
            LOG.info("[%s] fetch %s", source, snap_url)
            r = http_get(snap_url, session=session, client=client)
            time.sleep(DELAY_SECONDS)
            if r is None or r.status_code != 200:
                counters["fetch_failed"] += 1
                LOG.warning("[%s] snapshot fetch failed (%s)",
                            source, getattr(r, "status_code", "?"))
                continue
            html_bytes = r.content
            http_status = r.status_code
            actual_archive_url = r.url
            raw_path.write_bytes(html_bytes)
            if source == "taifaleo":
                metadata_path.write_text(json.dumps({
                    "requested_url": snap_url, "archive_url": actual_archive_url,
                    "http_status": http_status,
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                }, indent=2), encoding="utf-8")
            counters["snapshots_fetched"] += 1

        try:
            if source == "taifaleo":
                record = taifaleo.parse(html_bytes, actual_archive_url)
                if record is None:
                    counters["parse_failed"] += 1
                    continue
                record.update(
                    requested_url=snap_url, http_status=http_status,
                    discovery_method="wayback_cdx",
                    discovery_url=requests.Request("GET", CDX_ENDPOINT, params=cdx_params(
                        domain, from_date, to_date, cdx_limit)).prepare().url,
                    raw_snapshot_path=str(raw_path),
                )
            else:
                record = asdict(extract_article(html_bytes, source, original,
                                               timestamp, http_status))
        except Exception as e:
            counters["parse_failed"] += 1
            LOG.exception("[%s] parse error on %s: %s", source, snap_url, e)
            continue

        if not record["article_text"] or len(record["article_text"]) < 200:
            counters["skipped_short"] += 1
            LOG.debug("[%s] body too short, skipping %s", source, snap_url)
            continue

        if record["content_hash"] in seen_hashes or record["canonical_url"] in seen_urls:
            counters["skipped_duplicate"] += 1
            LOG.debug("[%s] duplicate %s", source, record["canonical_url"])
            continue

        seen_hashes.add(record["content_hash"])
        seen_urls.add(record["canonical_url"])

        with jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        counters["articles_written"] += 1

    manifest_path.write_text(
        json.dumps(counters, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    LOG.info("[%s] wrote %d articles (%d fetched, %d reused, %d dups, "
             "%d short, %d fetch-fail)",
             source, counters["articles_written"], counters["snapshots_fetched"],
             counters["snapshots_reused"], counters["skipped_duplicate"],
             counters["skipped_short"], counters["fetch_failed"])
    return counters


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Wayback Machine trial scraper for Kenyan news sources.",
    )
    p.add_argument("--sources", nargs="*", default=list(SOURCES.keys()),
                   choices=list(SOURCES.keys()),
                   help="which publishers to scan (default: all)")
    p.add_argument("--months", type=int, default=3,
                   help="how many months back to look (default: 3)")
    p.add_argument("--end", default=None,
                   help="end date YYYY-MM-DD (default: today UTC)")
    p.add_argument("--all-dates", action="store_true",
                   help="omit capture date bounds, matching the supplied Taifa Leo CDX query")
    p.add_argument("--limit", type=int, default=2000,
                   help="max CDX rows to pull per source (default 2000)")
    p.add_argument("--max-articles", type=int, default=200,
                   help="max articles to save per source (default 200)")
    p.add_argument("--max-fetches", type=int, default=0,
                   help="max snapshot retrieval attempts per source (0 means uncapped)")
    p.add_argument("--raw-root", default=str(ROOT / "data/trials/raw"),
                   help="root for raw snapshots (default data/trials/raw)")
    p.add_argument("--processed-root", default=str(ROOT / "data/trials/processed"),
                   help="root for normalized JSONL "
                        "(default data/trials/processed)")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()
    if args.months < 1 or args.limit < 1 or args.max_articles < 1 or args.max_fetches < 0:
        p.error("months, limit, and max-articles must be positive; max-fetches must be nonnegative")
    if args.all_dates and args.end:
        p.error("--all-dates cannot be combined with --end")
    return args


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.end:
        end = datetime.strptime(args.end, "%Y-%m-%d").replace(
            tzinfo=timezone.utc)
    else:
        end = datetime.now(timezone.utc)
    start = end - timedelta(days=30 * args.months)
    from_date = None if args.all_dates else start.strftime("%Y%m%d")
    to_date = None if args.all_dates else end.strftime("%Y%m%d")

    raw_root = Path(args.raw_root)
    processed_root = Path(args.processed_root)
    raw_root.mkdir(parents=True, exist_ok=True)
    processed_root.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    total = 0
    summary = []
    failed = False
    for src in args.sources:
        client = None
        if src == "taifaleo":
            client = Client(taifaleo.HOSTS, DELAY_SECONDS, USER_AGENT,
                            url_validator=taifaleo.accepts_fetch)
            client.source = src
        try:
            counters = process_source(
                source=src,
                domain=SOURCES[src],
                from_date=from_date,
                to_date=to_date,
                raw_root=raw_root,
                processed_root=processed_root,
                cdx_limit=args.limit,
                max_articles=args.max_articles,
                session=session,
                max_fetches=args.max_fetches, client=client,
            )
            summary.append(counters)
            total += counters["articles_written"]
        except KeyboardInterrupt:
            LOG.warning("interrupted by user")
            failed = True
            break
        except Exception as e:
            LOG.exception("[%s] failed: %s", src, e)
            failed = True
            failure = {"source": src, "status": "failed", "cdx_rows": None,
                       "error_type": type(e).__name__,
                       "finished_at": datetime.now(timezone.utc).isoformat()}
            if client is not None:
                failure["request_failure"] = client.last_failure
            (processed_root / f"{src}.manifest.json").write_text(
                json.dumps(failure, indent=2), encoding="utf-8")
            summary.append(failure)
        finally:
            if client is not None:
                client.session.close()

    LOG.info("done: %d articles saved; raw=%s processed=%s",
             total, raw_root, processed_root)
    print(json.dumps({"total_written": total, "per_source": summary},
                     indent=2, ensure_ascii=False))
    session.close()
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
