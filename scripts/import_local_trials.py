"""Import local JSON/JSONL trials and raw evidence without refetching publishers."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from database.repositories.articles import parse_timestamp
from scrapers.archive import archive_parts
from scrapers.common import allowed_url, normalize_url
from scripts.trial_scraper import SOURCES, build_services


def local_records(processed_root):
    """Read article inputs; manifests and other operational JSON are not articles."""
    records = []
    for path in sorted(processed_root.glob("*.jsonl")):
        if path.stem not in SOURCES:
            continue
        with path.open(encoding="utf-8") as handle:
            for number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    record, error = json.loads(line), None
                except ValueError as exc:
                    record, error = None, exc
                records.append((path.stem, path.name, number, record, error))
    for path in sorted(processed_root.glob("*.json")):
        if path.name.endswith(".manifest.json"):
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            records.append((None, path.name, 1, None, exc))
            continue
        if not isinstance(record, dict) or "article_text" not in record:
            continue
        source = record.get("source")
        records.append((source if isinstance(source, str) else None, path.name, 1, record, None))
    return records


def prepare_record(record, source, raw_root):
    """Validate local data and resolve only raw files inside the selected root."""
    if source not in SOURCES or not isinstance(record, dict) or record.get("source") != source:
        raise ValueError("Unsupported or mismatched record source")
    item = dict(record)
    publisher = SOURCES[source]
    hosts = publisher.PUBLISHER_HOSTS
    # Preserve the original, explicitly marked corporate trial without treating it
    # as Daily Nation reporting or relaxing the reporting publisher's host rules.
    if source == "nation" and item.get("content_scope") == "corporate_news":
        hosts = ("nationmedia.com", "www.nationmedia.com")
    for field in ("url", "canonical_url"):
        if not isinstance(item.get(field), str) or not allowed_url(item[field], hosts):
            raise ValueError("Missing or off-publisher article URL")
        item[field] = normalize_url(item[field])
    for field in ("title", "article_text", "parser_version", "scraped_at"):
        if not isinstance(item.get(field), str) or not item[field].strip():
            raise ValueError("Missing required article field")
    if parse_timestamp(item["scraped_at"]) is None:
        raise ValueError("Collection timestamp must include a timezone")
    digest = hashlib.sha256(item["article_text"].encode("utf-8")).hexdigest()
    if item.get("content_hash") != digest:
        raise ValueError("Article text does not match its recorded content hash")

    # Older generic Wayback records omit raw_snapshot_path. Reproduce the original
    # filename from the requested capture; do not claim it is the actual replay.
    timestamp = item.get("wayback_timestamp", "")
    requested = item.get("requested_url")
    if not requested and isinstance(timestamp, str) and re.fullmatch(r"\d{14}", timestamp):
        requested = f"https://web.archive.org/web/{timestamp}id_/{item['url']}"
        item["requested_url"] = requested
    raw_root = Path(raw_root).resolve()
    saved_path = item.get("raw_snapshot_path") or item.get("raw_snapshot")
    if saved_path:
        if not isinstance(saved_path, str):
            raise ValueError("Invalid raw snapshot path")
        saved = Path(saved_path)
        candidates = [saved] if saved.is_absolute() else [ROOT / saved, raw_root.parent.parent / saved]
        candidates.append(raw_root / source / saved.name)
    elif requested and archive_parts(requested, hosts):
        name = hashlib.sha1(requested.encode("utf-8")).hexdigest()[:16] + ".html"
        candidates = [raw_root / source / name]
    else:
        raise ValueError("Cannot identify raw snapshot")
    path = next((candidate.resolve() for candidate in candidates
                 if candidate.resolve().is_relative_to(raw_root)
                 and candidate.is_file()), None)
    if path is None:
        raise ValueError("Raw snapshot is missing or outside selected raw root")
    raw = path.read_bytes()
    if not raw:
        raise ValueError("Raw snapshot is empty")
    item["raw_snapshot_path"] = str(path)

    published = item.get("published_at") or ""
    try:
        publication_date = date.fromisoformat(published[:10])
    except (TypeError, ValueError):
        item.pop("publication_month", None)
        item["publication_date_needs_review"] = True
        item.setdefault("published_at_raw", published)
        item["published_at"] = ""
    else:
        item["publication_month"] = publication_date.strftime("%Y-%m")
        item["publication_date_needs_review"] = bool(
            item.get("publication_date_needs_review") or parse_timestamp(published) is None
        )
    item.setdefault("published_at_raw", published)
    item.setdefault("publication_timezone", "unknown" if parse_timestamp(published) is None else "explicit")
    item["kenya_relevance"] = "needs_review"
    item.pop("collection_run", None)
    return item, raw


def import_trials(processed_root, raw_root, sources=None, run_name="local-trial-import",
                  dry_run=False, services=None):
    processed_root, raw_root = Path(processed_root).resolve(), Path(raw_root).resolve()
    if not processed_root.is_dir() or not raw_root.is_dir():
        raise ValueError("Processed and raw roots must exist")
    records = local_records(processed_root)
    available = {source for source, *_ in records if source in SOURCES}
    selected = sorted(set(sources) if sources else available)
    if not selected or any(name not in SOURCES for name in selected):
        raise ValueError("No supported publisher article files selected")
    if any(name not in available for name in selected):
        raise ValueError("Selected publisher article files are missing")
    config = {"kind": "local_trial_import", "sources": selected,
              "processed_root": str(processed_root), "raw_root": str(raw_root),
              "input_formats": ["json", "jsonl"]}
    summary = {"dry_run": dry_run, "checked": 0, "ready": 0,
               "saved": 0, "duplicates": 0, "failed": 0, "errors": []}
    urls, hashes = set(), set()
    if not dry_run:
        persistence, articles, runs = services or build_services()
    else:
        from contextlib import nullcontext
    # Serialize local imports even across different run names. Database constraints
    # additionally protect identical article/version inserts.
    context = nullcontext() if dry_run else runs.lock("local-trial-import")
    with context:
        if not dry_run:
            run_id = runs.resolve(run_name, config)
            urls, hashes = articles.existing_identities()
        try:
            for source, filename, number, record, error in records:
                if sources and source not in selected:
                    continue
                summary["checked"] += 1
                try:
                    if error is not None:
                        raise error
                    item, raw = prepare_record(record, source, raw_root)
                    identity = item["canonical_url"]
                    content = (source, item["content_hash"])
                    if identity in urls or item["url"] in urls or content in hashes:
                        summary["duplicates"] += 1
                        continue
                    if dry_run:
                        summary["ready"] += 1
                    else:
                        # Use a stable local timestamp fallback so retrying a
                        # missing-date record next month cannot create new paths.
                        month = item.get("publication_month") or item["scraped_at"][:7]
                        raw_ref = persistence.store_raw(source, identity, raw, month)
                        created = persistence.persist_article(item, raw_ref, run_id)
                        summary["saved" if created else "duplicates"] += 1
                    urls.update((identity, item["url"]))
                    hashes.add(content)
                except Exception as exc:
                    summary["failed"] += 1
                    # Avoid credentials, article content, or victim identifiers
                    # from exception messages in operational summaries.
                    summary["errors"].append({"source": source, "file": filename, "line": number,
                                              "error": type(exc).__name__})
            summary["status"] = "finished_with_gaps" if summary["failed"] else "completed"
            if not dry_run:
                persistence.objects.write_json("runs", f"runs/{run_name}/import_summary.json", summary)
                runs.set_status(run_id, summary["status"])
        except BaseException:
            if not dry_run:
                runs.set_status(run_id, "interrupted")
            raise
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-root", type=Path, default=ROOT / "data/trials/processed")
    parser.add_argument("--raw-root", type=Path, default=ROOT / "data/trials/raw")
    parser.add_argument("--source", action="append", choices=sorted(SOURCES))
    parser.add_argument("--run-name", default="local-trial-import")
    parser.add_argument("--dry-run", action="store_true", help="Validate locally without cloud access")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", args.run_name):
        parser.error("Run name must be a simple identifier")
    try:
        summary = import_trials(args.processed_root, args.raw_root, args.source,
                                args.run_name, args.dry_run)
    except Exception as exc:
        print(f"Import stopped ({type(exc).__name__}); check input roots and infrastructure configuration.",
              file=sys.stderr)
        return 2
    print(json.dumps(summary, indent=2))
    return 2 if summary["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
