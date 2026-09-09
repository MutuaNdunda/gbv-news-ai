"""Grouped dashboard queries; no GCS listing is used for corpus counts."""

from sqlalchemy import desc, func, select

from database.models import Article, ArticleVersion, CollectionRun


class DashboardService:
    def __init__(self, sessions):
        self.sessions = sessions

    def overview(self):
        problem = {"failed", "interrupted", "paused_index_unavailable", "finished_with_gaps"}
        with self.sessions() as session:
            totals = {
                "articles": session.scalar(select(func.count()).select_from(Article)),
                "versions": session.scalar(select(func.count()).select_from(ArticleVersion)),
                "runs": session.scalar(select(func.count()).select_from(CollectionRun)),
                "active_runs": session.scalar(select(func.count()).select_from(CollectionRun).where(CollectionRun.status == "running")),
                "problem_runs": session.scalar(select(func.count()).select_from(CollectionRun).where(CollectionRun.status.in_(problem))),
            }
            by_source = session.execute(select(Article.source, func.count()).group_by(Article.source).order_by(Article.source)).all()
            by_month = session.execute(select(ArticleVersion.publication_month, func.count()).where(ArticleVersion.publication_month.is_not(None)).group_by(ArticleVersion.publication_month).order_by(ArticleVersion.publication_month)).all()
            recent_runs = session.execute(select(CollectionRun).order_by(desc(CollectionRun.started_at)).limit(8)).scalars().all()
            activity = session.execute(select(ArticleVersion, Article).join(Article).order_by(desc(ArticleVersion.scraped_at)).limit(10)).all()
        return {"totals": totals, "by_source": by_source, "by_month": by_month,
                "recent_runs": recent_runs, "activity": activity}
