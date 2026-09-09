"""Supabase persistence and lookup for logical articles and extraction lineage."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from database.models import Article, ArticleVersion


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def parse_month(value: Any) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value[:7] + "-01")
    except ValueError:
        return None


class ArticleRepository:
    def __init__(self, sessions: sessionmaker[Session]):
        self.sessions = sessions

    def existing_identities(self) -> tuple[set[str], set[tuple[str, str]]]:
        with self.sessions() as session:
            urls = {
                value
                for row in session.execute(
                    select(
                        Article.canonical_url,
                        ArticleVersion.requested_url,
                        ArticleVersion.archive_url,
                    ).outerjoin(ArticleVersion)
                )
                for value in row
                if value
            }
            hashes = set(
                session.execute(
                    select(Article.source, ArticleVersion.content_hash).join(ArticleVersion)
                ).all()
            )
        return urls, hashes

    def persist(
        self,
        article: dict,
        run_id: UUID,
        raw_uri: str,
        raw_generation: str | None,
        processed_uri: str,
        processed_generation: str | None,
    ) -> tuple[UUID, bool]:
        """Upsert an article and resolve its idempotent version in one transaction."""
        article_values = {
            "article_id": article["article_id"],
            "source": article["source"],
            "canonical_url": article["canonical_url"],
            "title": article["title"],
            "author": article.get("author") or None,
            "published_at": parse_timestamp(article.get("published_at")),
            "published_at_raw": article.get("published_at_raw"),
            "publication_timezone": article.get("publication_timezone"),
            "language": article.get("language") or None,
            "section": article.get("section") or None,
            "publisher_name": article.get("publisher_name"),
            "publisher_domain": article.get("publisher_domain"),
            "content_scope": article.get("content_scope"),
            "kenya_relevance": article.get("kenya_relevance", "needs_review"),
            "kenya_relevance_basis": article.get("kenya_relevance_basis"),
            "publication_date_needs_review": bool(
                article.get("publication_date_needs_review", False)
            ),
        }
        update_values = {
            key: value
            for key, value in article_values.items()
            if key not in {"article_id", "source", "canonical_url", "kenya_relevance"}
        }
        version_values = {
            "collection_run_id": run_id,
            "content_hash": article["content_hash"],
            "parser_version": article["parser_version"],
            "scraped_at": parse_timestamp(article["scraped_at"]),
            "raw_object_uri": raw_uri,
            "processed_object_uri": processed_uri,
            "raw_object_generation": raw_generation,
            "processed_object_generation": processed_generation,
            "requested_url": article.get("requested_url"),
            "archive_url": article.get("archive_url"),
            "archive_capture_timestamp": article.get("archive_capture_timestamp"),
            "discovery_url": article.get("discovery_url"),
            "discovery_method": article.get("discovery_method"),
            "discovery_capture_month": parse_month(article.get("discovery_capture_month")),
            "publication_month": parse_month(article.get("publication_month")),
            "http_status": article.get("http_status"),
            "processing_status": "indexed",
            "processing_error": None,
        }
        with self.sessions.begin() as session:
            article_uuid = session.execute(
                insert(Article)
                .values(**article_values)
                .on_conflict_do_update(
                    index_elements=[Article.source, Article.canonical_url],
                    set_=update_values,
                )
                .returning(Article.id)
            ).scalar_one()
            statement = (
                insert(ArticleVersion)
                .values(article_id=article_uuid, **version_values)
                .on_conflict_do_nothing(
                    index_elements=[
                        ArticleVersion.article_id,
                        ArticleVersion.content_hash,
                        ArticleVersion.parser_version,
                    ]
                )
                .returning(ArticleVersion.id)
            )
            version_uuid = session.execute(statement).scalar_one_or_none()
            if version_uuid is None:
                version_uuid = session.execute(
                    select(ArticleVersion.id).where(
                        ArticleVersion.article_id == article_uuid,
                        ArticleVersion.content_hash == article["content_hash"],
                        ArticleVersion.parser_version == article["parser_version"],
                    )
                ).scalar_one()
                return version_uuid, False
            return version_uuid, True

    def counts(
        self, sources: list[str], months: list[str], run_id: UUID | None = None
    ) -> dict[tuple[str, str], int]:
        result = {(source, month): 0 for source in sources for month in months}
        with self.sessions() as session:
            statement = (
                select(Article.source, ArticleVersion.publication_month, func.count())
                .join(ArticleVersion)
                .where(
                    Article.source.in_(sources),
                    ArticleVersion.publication_month.in_([parse_month(m) for m in months]),
                    or_(Article.content_scope.is_(None), Article.content_scope != "corporate_news"),
                )
                .group_by(Article.source, ArticleVersion.publication_month)
            )
            if run_id is not None:
                statement = statement.where(ArticleVersion.collection_run_id == run_id)
            for source, month, count in session.execute(statement):
                result[(source, month.strftime("%Y-%m"))] = count
        return result
