"""Coordinate durable GCS objects with Supabase article lineage."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from typing import Any
from uuid import UUID

from storage.gcs import ObjectReference


class IndexingError(RuntimeError):
    """Database indexing failed after both GCS artifacts became durable."""

    def __init__(self, pending: dict):
        super().__init__("Supabase indexing failed after GCS persistence")
        self.pending = pending


def article_identifier(source: str, canonical_url: str) -> str:
    return hashlib.sha256(f"{source}:{canonical_url}".encode()).hexdigest()


def object_month(value: str | None) -> str:
    if value and len(value) >= 7 and value[4] == "-":
        return value[:7]
    return datetime.now(timezone.utc).strftime("%Y-%m")


class CollectionPersistence:
    def __init__(self, objects: Any, articles: Any):
        self.objects = objects
        self.articles = articles

    def store_raw(self, source: str, identity_url: str, raw_html: bytes | str,
                  month: str | None = None) -> ObjectReference:
        """Persist raw evidence before parsing or database indexing."""
        identifier = article_identifier(source, identity_url)
        year, number = object_month(month).split("-")
        name = f"{source}/{year}/{number}/{identifier}.html"
        payload = raw_html if isinstance(raw_html, bytes) else raw_html.encode("utf-8")
        return self.objects.write_bytes(
            "raw", name, payload, "text/html; charset=utf-8", create_only=True
        )

    def persist_article(self, article: dict, raw: ObjectReference, run_id: UUID) -> bool:
        """Write normalized JSON, then transactionally index its database lineage."""
        article["article_id"] = article_identifier(article["source"], article["canonical_url"])
        article["raw_object_uri"] = raw.uri
        article["raw_object_generation"] = raw.generation
        month = article.get("publication_month") or article.get("published_at")
        year, number = object_month(month).split("-")
        name = (f"{article['parser_version']}/{article['source']}/{year}/{number}/"
                f"{article['article_id']}.json")
        processed_article = dict(article)
        # Run linkage belongs in Supabase; keeping it out of the canonical processed
        # object makes an identical extraction byte-for-byte idempotent across retries.
        processed_article.pop("collection_run", None)
        processed = self.objects.write_json(
            "processed", name, processed_article, create_only=True
        )
        try:
            _, created = self.articles.persist(
                article, run_id, raw.uri, raw.generation,
                processed.uri, processed.generation,
            )
        except Exception as exc:
            raise IndexingError({
                "processed_object_name": name,
                "processed_object_uri": processed.uri,
                "processed_object_generation": processed.generation,
                "raw_object_uri": raw.uri,
                "raw_object_generation": raw.generation,
            }) from exc
        return created

    def retry_index(self, pending: dict, run_id: UUID) -> bool:
        """Index an already-durable extraction without refetching its source."""
        article = self.objects.read_json(
            "processed", pending["processed_object_name"]
        )
        if article is None:
            raise RuntimeError("Pending processed GCS object is missing")
        _, created = self.articles.persist(
            article,
            run_id,
            pending["raw_object_uri"],
            pending.get("raw_object_generation"),
            pending["processed_object_uri"],
            pending.get("processed_object_generation"),
        )
        return created
