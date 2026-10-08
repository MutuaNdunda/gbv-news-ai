"""Collection-run list and detail queries."""

from datetime import datetime, timezone

from sqlalchemy import desc, func, select, inspect
from sqlalchemy.orm import undefer

from database.repositories.collection_runs import CollectionRunRepository, RUN_STATUSES, utc

from database.models import ArticleVersion, CollectionRun, CollectionRunScan


class RunService:
    def __init__(self, sessions):
        self.sessions = sessions
        self._ready = None

    def control_ready(self):
        if self._ready is None:
            columns = {c['name'] for c in inspect(self.sessions.kw['bind']).get_columns('collection_runs', schema='public')}
            self._ready = {'last_heartbeat_at', 'stop_requested_at', 'stop_requested_reason',
                           'finalization_reason', 'worker_token'} <= columns
        return self._ready

    def list(self, page=1, per_page=25, status=""):
        status = status if status in RUN_STATUSES else ""
        version_counts = select(ArticleVersion.collection_run_id.label("run_id"), func.count().label("article_count")).group_by(ArticleVersion.collection_run_id).subquery()
        scan_counts = select(CollectionRunScan.collection_run_id.label("run_id"), func.count().label("scan_count"), func.count().filter(CollectionRunScan.status == "index_exhausted").label("complete_scans")).group_by(CollectionRunScan.collection_run_id).subquery()
        statement = select(CollectionRun, func.coalesce(version_counts.c.article_count, 0), func.coalesce(scan_counts.c.complete_scans, 0), func.coalesce(scan_counts.c.scan_count, 0)).outerjoin(version_counts, version_counts.c.run_id == CollectionRun.id).outerjoin(scan_counts, scan_counts.c.run_id == CollectionRun.id).order_by(desc(CollectionRun.started_at))
        if self.control_ready():
            statement = statement.options(undefer("*"))
        count = select(func.count()).select_from(CollectionRun)
        if status:
            statement = statement.where(CollectionRun.status == status)
            count = count.where(CollectionRun.status == status)
        with self.sessions() as session:
            total = session.scalar(count)
            rows = session.execute(statement.offset((page - 1) * per_page).limit(per_page)).all()
        return rows, total

    def detail(self, run_id):
        with self.sessions() as session:
            run = session.get(CollectionRun, run_id, options=[undefer("*")] if self.control_ready() else [])
            if run is None:
                return None
            scans = session.execute(select(CollectionRunScan).where(CollectionRunScan.collection_run_id == run_id).order_by(CollectionRunScan.source, CollectionRunScan.capture_month.desc())).scalars().all()
            versions = session.scalar(select(func.count()).select_from(ArticleVersion).where(ArticleVersion.collection_run_id == run_id))
        return {"run": run, "scans": scans, "version_count": versions}

    def request_stop(self, run_id):
        if not self.control_ready():
            return "unavailable"
        return CollectionRunRepository(self.sessions).request_stop(run_id)


def control_value(run, name):
    # Deferred control fields let monitors continue reading a pre-migration target.
    state = inspect(run, raiseerr=False)
    if state is not None and name in state.unloaded:
        return None
    return getattr(run, name, None)


def run_liveness(run, stale_seconds=1800, now=None):
    """Read-only operational display; elapsed duration never establishes death."""
    now = now or datetime.now(timezone.utc)
    heartbeat = control_value(run, 'last_heartbeat_at')
    stop = control_value(run, 'stop_requested_at')
    label = RUN_STATUSES.get(run.status, run.status)
    possibly_stalled = run.status == 'running' and (heartbeat is None or
        (now - utc(heartbeat)).total_seconds() > stale_seconds)
    if run.status == 'running':
        label = 'Stop requested' if stop else 'Possibly stalled' if possibly_stalled else 'Running'
    end = getattr(run, 'finished_at', None) or now
    elapsed = max(0, int((utc(end) - utc(run.started_at)).total_seconds()))
    return dict(label=label, heartbeat=heartbeat, stop_requested=stop is not None,
                managed=control_value(run, 'worker_token') is not None,
                possibly_stalled=possibly_stalled, elapsed=f'{elapsed // 3600}h {(elapsed % 3600) // 60}m',
                reason=control_value(run, 'finalization_reason'))
