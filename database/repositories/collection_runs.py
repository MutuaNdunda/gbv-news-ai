"""Supabase persistence for collection-run lifecycle state."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from database.models import CollectionRun


def month_date(value: str | None) -> date | None:
    return date.fromisoformat(value + "-01") if value else None


class CollectionRunRepository:
    def __init__(self, sessions: sessionmaker[Session]):
        self.sessions = sessions

    def resolve(self, run_name: str, configuration: dict) -> UUID:
        values = {
            "run_name": run_name,
            "status": "running",
            "start_month": month_date(configuration.get("start_month")),
            "end_month": month_date(configuration.get("end_month")),
            "configuration": configuration,
        }
        with self.sessions.begin() as session:
            session.execute(
                insert(CollectionRun).values(**values).on_conflict_do_nothing(
                    index_elements=[CollectionRun.run_name]
                )
            )
            run = session.execute(
                select(CollectionRun).where(CollectionRun.run_name == run_name)
            ).scalar_one()
            if run.configuration != configuration:
                raise ValueError("Resume configuration differs from saved run")
            run.status = "running"
            run.finished_at = None
            return run.id

    def set_status(self, run_id: UUID, status: str) -> None:
        terminal = status in {
            "interrupted", "paused_index_unavailable", "finished_with_gaps",
            "index_scans_finished", "completed", "failed",
        }
        with self.sessions.begin() as session:
            session.execute(
                update(CollectionRun)
                .where(CollectionRun.id == run_id)
                .values(
                    status=status,
                    finished_at=datetime.now(timezone.utc) if terminal else None,
                )
            )

    @contextmanager
    def lock(self, run_name: str):
        """Prevent two collectors from mutating one durable run concurrently."""
        engine = self.sessions.kw["bind"]
        with engine.connect() as connection:
            acquired = connection.execute(
                text("SELECT pg_try_advisory_lock(hashtextextended(:name, 0))"),
                {"name": run_name},
            ).scalar_one()
            if not acquired:
                raise RuntimeError("This run name is already being collected")
            try:
                yield
            finally:
                connection.execute(
                    text("SELECT pg_advisory_unlock(hashtextextended(:name, 0))"),
                    {"name": run_name},
                )
