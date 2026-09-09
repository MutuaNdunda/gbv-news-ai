"""Collection-run list and detail queries."""

from sqlalchemy import desc, func, select

from database.models import ArticleVersion, CollectionRun, CollectionRunScan


class RunService:
    def __init__(self, sessions):
        self.sessions = sessions

    def list(self, page=1, per_page=25):
        version_counts = select(ArticleVersion.collection_run_id.label("run_id"), func.count().label("article_count")).group_by(ArticleVersion.collection_run_id).subquery()
        scan_counts = select(CollectionRunScan.collection_run_id.label("run_id"), func.count().label("scan_count"), func.count().filter(CollectionRunScan.status == "index_exhausted").label("complete_scans")).group_by(CollectionRunScan.collection_run_id).subquery()
        statement = select(CollectionRun, func.coalesce(version_counts.c.article_count, 0), func.coalesce(scan_counts.c.complete_scans, 0), func.coalesce(scan_counts.c.scan_count, 0)).outerjoin(version_counts, version_counts.c.run_id == CollectionRun.id).outerjoin(scan_counts, scan_counts.c.run_id == CollectionRun.id).order_by(desc(CollectionRun.started_at))
        with self.sessions() as session:
            total = session.scalar(select(func.count()).select_from(CollectionRun))
            rows = session.execute(statement.offset((page - 1) * per_page).limit(per_page)).all()
        return rows, total

    def detail(self, run_id):
        with self.sessions() as session:
            run = session.get(CollectionRun, run_id)
            if run is None:
                return None
            scans = session.execute(select(CollectionRunScan).where(CollectionRunScan.collection_run_id == run_id).order_by(CollectionRunScan.source, CollectionRunScan.capture_month.desc())).scalars().all()
            versions = session.scalar(select(func.count()).select_from(ArticleVersion).where(ArticleVersion.collection_run_id == run_id))
        return {"run": run, "scans": scans, "version_count": versions}
