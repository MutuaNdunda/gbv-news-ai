"""Paginated article search and lineage detail queries."""

from datetime import date
from uuid import UUID

from sqlalchemy import cast, Date, func, or_, select

from database.models import Article, ArticleVersion, CollectionRun
from database.repositories.articles import parse_month


class ArticleService:
    def __init__(self, sessions):
        self.sessions = sessions

    def list(self, filters, page=1, per_page=25):
        conditions = []
        if filters.get("source"):
            conditions.append(Article.source == filters["source"])
        if filters.get("kenya_relevance"):
            conditions.append(Article.kenya_relevance == filters["kenya_relevance"])
        if filters.get("date"):
            try:
                conditions.append(cast(Article.published_at, Date) == date.fromisoformat(filters["date"]))
            except ValueError:
                pass
        if filters.get("q"):
            term = f"%{filters['q']}%"
            conditions.append(or_(Article.title.ilike(term), Article.canonical_url.ilike(term), Article.article_id.ilike(term)))
        version_filters = []
        if filters.get("month"):
            version_filters.append(ArticleVersion.publication_month == parse_month(filters["month"]))
        if filters.get("parser_version"):
            version_filters.append(ArticleVersion.parser_version == filters["parser_version"])
        if filters.get("run_id"):
            try:
                version_filters.append(ArticleVersion.collection_run_id == UUID(filters["run_id"]))
            except ValueError:
                pass
        if version_filters:
            conditions.append(select(ArticleVersion.id).where(ArticleVersion.article_id == Article.id, *version_filters).exists())
        statement = select(Article).where(*conditions).order_by(Article.published_at.desc().nullslast(), Article.title)
        with self.sessions() as session:
            total = session.scalar(select(func.count()).select_from(statement.subquery()))
            rows = session.execute(statement.offset((page - 1) * per_page).limit(per_page)).scalars().all()
            runs = session.execute(select(CollectionRun.id, CollectionRun.run_name).order_by(CollectionRun.run_name)).all()
            parsers = session.scalars(select(ArticleVersion.parser_version).distinct().order_by(ArticleVersion.parser_version)).all()
        return rows, total, runs, parsers

    def detail(self, article_id):
        with self.sessions() as session:
            article = session.get(Article, article_id)
            if article is None:
                return None
            versions = session.execute(select(ArticleVersion, CollectionRun.run_name).outerjoin(CollectionRun, CollectionRun.id == ArticleVersion.collection_run_id).where(ArticleVersion.article_id == article_id).order_by(ArticleVersion.scraped_at.desc())).all()
        return {"article": article, "versions": versions}
