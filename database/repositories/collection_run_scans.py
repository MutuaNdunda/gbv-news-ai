"""Idempotent operational progress updates for monthly source scans."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from database.models import CollectionRunScan
from database.repositories.articles import parse_timestamp
from database.repositories.collection_runs import month_date


TERMINAL_SCAN_STATUSES = {
    "index_exhausted", "index_exhausted_with_gaps", "fetch_limit",
    "index_page_limit", "index_failed",
}


class CollectionRunScanRepository:
    def __init__(self, sessions: sessionmaker[Session]):
        self.sessions = sessions

    def update(self, run_id: UUID, source: str, capture_month: str, scan: dict) -> None:
        now = datetime.now(timezone.utc)
        values = {
            "collection_run_id": run_id,
            "source": source,
            "capture_month": month_date(capture_month),
            "status": scan["status"],
            "index_pages": scan.get("index_pages", 0),
            "candidate_count": scan.get("candidates", 0),
            "fetch_attempts": scan.get("attempted", 0),
            "articles_saved": scan.get("saved", 0),
            "duplicates_skipped": scan.get("duplicates", 0),
            "errors_count": scan.get("failed", 0),
            "started_at": parse_timestamp(scan.get("started_at")),
            "finished_at": now if scan["status"] in TERMINAL_SCAN_STATUSES else None,
            "updated_at": now,
        }
        if scan["status"] == "running" and values["started_at"] is None:
            values["started_at"] = now
            scan["started_at"] = now.isoformat()
        excluded = insert(CollectionRunScan).excluded
        updates = {key: getattr(excluded, key) for key in values
                   if key not in {"collection_run_id", "source", "capture_month", "started_at"}}
        updates["started_at"] = CollectionRunScan.started_at
        with self.sessions.begin() as session:
            session.execute(
                insert(CollectionRunScan).values(**values).on_conflict_do_update(
                    index_elements=[CollectionRunScan.collection_run_id,
                                    CollectionRunScan.source,
                                    CollectionRunScan.capture_month],
                    set_=updates,
                )
            )
