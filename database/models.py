"""SQLAlchemy mappings for the existing Supabase ingestion schema."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CollectionRun(Base):
    __tablename__ = "collection_runs"
    __table_args__ = {"schema": "public"}

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    run_name: Mapped[str] = mapped_column(Text, unique=True)
    status: Mapped[str] = mapped_column(Text)
    start_month: Mapped[date | None] = mapped_column(Date)
    end_month: Mapped[date | None] = mapped_column(Date)
    configuration: Mapped[dict] = mapped_column(JSONB)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (UniqueConstraint("source", "canonical_url"), {"schema": "public"})

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    article_id: Mapped[str] = mapped_column(Text, unique=True)
    source: Mapped[str] = mapped_column(Text)
    canonical_url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at_raw: Mapped[str | None] = mapped_column(Text)
    publication_timezone: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(Text)
    section: Mapped[str | None] = mapped_column(Text)
    publisher_name: Mapped[str | None] = mapped_column(Text)
    publisher_domain: Mapped[str | None] = mapped_column(Text)
    content_scope: Mapped[str | None] = mapped_column(Text)
    kenya_relevance: Mapped[str] = mapped_column(Text)
    kenya_relevance_basis: Mapped[str | None] = mapped_column(Text)
    publication_date_needs_review: Mapped[bool] = mapped_column(Boolean)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ArticleVersion(Base):
    __tablename__ = "article_versions"
    __table_args__ = (
        UniqueConstraint("article_id", "content_hash", "parser_version"),
        {"schema": "public"},
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    article_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("public.articles.id", ondelete="CASCADE")
    )
    collection_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("public.collection_runs.id", ondelete="SET NULL"),
    )
    content_hash: Mapped[str] = mapped_column(Text)
    parser_version: Mapped[str] = mapped_column(Text)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    raw_object_uri: Mapped[str] = mapped_column(Text)
    processed_object_uri: Mapped[str | None] = mapped_column(Text)
    raw_object_generation: Mapped[str | None] = mapped_column(Text)
    processed_object_generation: Mapped[str | None] = mapped_column(Text)
    requested_url: Mapped[str | None] = mapped_column(Text)
    archive_url: Mapped[str | None] = mapped_column(Text)
    archive_capture_timestamp: Mapped[str | None] = mapped_column(Text)
    discovery_url: Mapped[str | None] = mapped_column(Text)
    discovery_method: Mapped[str | None] = mapped_column(Text)
    discovery_capture_month: Mapped[date | None] = mapped_column(Date)
    publication_month: Mapped[date | None] = mapped_column(Date)
    http_status: Mapped[int | None] = mapped_column(Integer)
    processing_status: Mapped[str] = mapped_column(Text)
    processing_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CollectionRunScan(Base):
    __tablename__ = "collection_run_scans"
    __table_args__ = (
        UniqueConstraint("collection_run_id", "source", "capture_month"),
        CheckConstraint("source IN ('nation','citizen','standard','star')", name="collection_run_scans_source_check"),
        CheckConstraint("status IN ('pending','running','index_exhausted','index_exhausted_with_gaps','fetch_limit','index_page_limit','index_failed')", name="collection_run_scans_status_check"),
        Index("idx_collection_run_scans_collection_run_id", "collection_run_id"),
        Index("idx_collection_run_scans_source", "source"),
        Index("idx_collection_run_scans_capture_month", "capture_month"),
        Index("idx_collection_run_scans_status", "status"),
        {"schema": "public"},
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    collection_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("public.collection_runs.id", ondelete="CASCADE"),
    )
    source: Mapped[str] = mapped_column(Text)
    capture_month: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Text)
    index_pages: Mapped[int] = mapped_column(Integer)
    candidate_count: Mapped[int] = mapped_column(Integer)
    fetch_attempts: Mapped[int] = mapped_column(Integer)
    articles_saved: Mapped[int] = mapped_column(Integer)
    duplicates_skipped: Mapped[int] = mapped_column(Integer)
    errors_count: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
