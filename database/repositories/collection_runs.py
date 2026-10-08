"""Collection lifecycle, cooperative control and ownership-checked reconciliation."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timezone, timedelta
import logging
from uuid import UUID, uuid4

from sqlalchemy import select, text, update, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import undefer

from database.models import CollectionRun, CollectionRunScan, ArticleVersion

LOGGER = logging.getLogger(__name__)
RUN_STATUSES = {
    'running': 'Running', 'completed': 'Completed', 'interrupted': 'Interrupted',
    'failed': 'Failed', 'finished_with_gaps': 'Finished with gaps',
    'paused_index_unavailable': 'Paused / index unavailable',
    'index_scans_finished': 'Index scans finished',
}


class CollectionLockLost(RuntimeError):
    """No further writes are allowed after execution ownership is lost."""


class CollectionLockBusy(RuntimeError):
    pass


class CollectionLease:
    def __init__(self, connection, name, backend_id):
        self.connection, self.name, self.backend_id = connection, name, backend_id
        self.lost = False

    def check(self):
        if self.lost:
            raise CollectionLockLost('Collection lease was lost')
        try:
            backend, owns = self.connection.execute(text('''
                SELECT pg_backend_pid(), EXISTS (
                    SELECT 1 FROM pg_locks WHERE locktype = 'advisory'
                    AND pid = pg_backend_pid() AND granted AND objsubid = 1
                    AND mode = 'ExclusiveLock'
                    AND database = (SELECT oid FROM pg_database WHERE datname = current_database())
                    AND classid = ((hashtextextended(:name, 0) >> 32) & 4294967295)::oid
                    AND objid = (hashtextextended(:name, 0) & 4294967295)::oid
                )
            '''), {'name': self.name}).one()
            if backend != self.backend_id or not owns:
                raise CollectionLockLost('Collection backend or lock ownership changed')
        except (DBAPIError, CollectionLockLost) as exc:
            self.lost = True
            self.connection.invalidate()
            raise CollectionLockLost('Collection ownership unavailable') from exc


def month_date(value: str | None) -> date | None:
    return date.fromisoformat(value + '-01') if value else None


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def stale(run, now, seconds):
    # Missing legacy evidence never proves an orphan; started_at is not a heartbeat.
    return (run.status == 'running' and run.last_heartbeat_at is not None
            and utc(run.last_heartbeat_at) < utc(now) - timedelta(seconds=seconds))


class CollectionRunRepository:
    def __init__(self, sessions):
        self.sessions = sessions

    def resolve(self, run_name: str, configuration: dict, *, managed=False) -> UUID:
        values = dict(run_name=run_name, status='running',
                      start_month=month_date(configuration.get('start_month')),
                      end_month=month_date(configuration.get('end_month')), configuration=configuration)
        with self.sessions.begin() as session:
            session.execute(insert(CollectionRun).values(**values).on_conflict_do_nothing(
                index_elements=[CollectionRun.run_name]))
            run = session.execute(select(CollectionRun).where(
                CollectionRun.run_name == run_name).with_for_update()).scalar_one()
            if run.configuration != configuration:
                raise ValueError('Resume configuration differs from saved run')
            run.status, run.finished_at = 'running', None
            if managed:
                run.last_heartbeat_at = datetime.now(timezone.utc)
                run.stop_requested_at = run.stop_requested_reason = run.finalization_reason = None
                run.worker_token = uuid4()
            return run.id

    def control(self, run_id):
        with self.sessions() as session:
            return session.get(CollectionRun, run_id, options=[undefer("*")])

    def heartbeat(self, run_id, worker_token, now):
        with self.sessions.begin() as session:
            result = session.execute(update(CollectionRun).where(
                CollectionRun.id == run_id, CollectionRun.status == 'running',
                CollectionRun.worker_token == worker_token).values(last_heartbeat_at=now))
            if result.rowcount != 1:
                raise CollectionLockLost('Collection attempt is no longer current')

    def request_stop(self, run_id):
        with self.sessions.begin() as session:
            run = session.execute(select(CollectionRun).where(
                CollectionRun.id == run_id).with_for_update()).scalar_one_or_none()
            if run is None:
                return 'missing'
            if run.status != 'running':
                return 'inactive'
            if run.worker_token is None:
                return 'unsupported'
            if run.stop_requested_at is not None:
                return 'already_requested'
            run.stop_requested_at = datetime.now(timezone.utc)
            run.stop_requested_reason = 'user_requested_stop'
            return 'requested'

    def set_status(self, run_id: UUID, status: str, *, reason=None, worker_token=None):
        if status not in RUN_STATUSES:
            raise ValueError('Unsupported collection run status')
        conditions = [CollectionRun.id == run_id]
        if worker_token is not None:
            conditions.extend((CollectionRun.worker_token == worker_token, CollectionRun.status == 'running'))
        now = datetime.now(timezone.utc)
        with self.sessions.begin() as session:
            result = session.execute(update(CollectionRun).where(*conditions).values(
                status=status, finished_at=now if status != 'running' else None,
                finalization_reason=reason))
            if worker_token is not None and result.rowcount != 1:
                raise CollectionLockLost('Collection attempt changed before finalization')

    @contextmanager
    def lock(self, run_name):
        """Use the existing run-name key, on a dedicated autocommit session."""
        engine = self.sessions.kw['bind']
        if 'pooler' in (engine.url.host or '') and engine.url.port == 6543:
            raise RuntimeError('Collection requires direct PostgreSQL or session pooling')
        with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
            acquired, backend = connection.execute(text(
                'SELECT pg_try_advisory_lock(hashtextextended(:name, 0)), pg_backend_pid()'
            ), {'name': run_name}).one()
            if not acquired:
                raise CollectionLockBusy('This run name is already being collected')
            lease = CollectionLease(connection, run_name, backend)
            try:
                yield lease
            finally:
                try:
                    if not lease.lost:
                        connection.execute(text('SELECT pg_advisory_unlock(hashtextextended(:name, 0))'),
                                           {'name': run_name})
                except DBAPIError:
                    connection.invalidate()
                    LOGGER.warning('collection_lock_release_failed')

    def reconcile_stale_runs(self, *, apply=False, stale_seconds=1800, now=None):
        """Dry-run by default. Acquire the collector's exact key, then recheck."""
        if stale_seconds < 60:
            raise ValueError('Stale threshold must be at least 60 seconds')
        now = now or datetime.now(timezone.utc)
        with self.sessions() as session:
            runs = session.execute(select(CollectionRun).where(
                CollectionRun.status == 'running').options(undefer('*'))).scalars().all()
        summary = []
        for run in runs:
            item = dict(run_id=str(run.id), started_at=run.started_at.isoformat(),
                        last_heartbeat_at=run.last_heartbeat_at.isoformat() if run.last_heartbeat_at else None,
                        stop_requested=run.stop_requested_at is not None,
                        ownership='unknown', action='unchanged')
            with self.sessions() as session:
                item['articles'] = session.scalar(select(func.count()).select_from(ArticleVersion).where(ArticleVersion.collection_run_id == run.id))
                item['scans'] = [dict(source=s.source, month=str(s.capture_month), status=s.status,
                                      saved=s.articles_saved, fetches=s.fetch_attempts)
                                 for s in session.execute(select(CollectionRunScan).where(
                                     CollectionRunScan.collection_run_id == run.id)).scalars()]
            try:
                with self.lock(run.run_name) as lease:
                    item['ownership'] = 'no_owner'
                    with self.sessions.begin() as session:
                        current = session.execute(select(CollectionRun).where(
                            CollectionRun.id == run.id).with_for_update()).scalar_one()
                        # Restrict repairs to new managed attempts, never legacy missing evidence.
                        if current.worker_token and stale(current, now, stale_seconds):
                            item['action'] = 'would_interrupt'
                            if apply:
                                lease.check()
                                current.status, current.finished_at = 'interrupted', now
                                current.finalization_reason = 'stale_run_reconciled'
                                session.execute(update(CollectionRunScan).where(
                                    CollectionRunScan.collection_run_id == current.id,
                                    CollectionRunScan.status == 'running').values(
                                        status='pending', updated_at=now, finished_at=None))
                                item['action'] = 'interrupted'
            except CollectionLockBusy:
                item['ownership'] = 'active_lock'
            except (DBAPIError, CollectionLockLost):
                item['ownership'] = 'unavailable'
            summary.append(item)
        return summary
