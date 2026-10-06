"""Append-only annotation persistence and version-aware operational queries."""

from contextlib import contextmanager
from datetime import datetime, timezone
import logging
from uuid import uuid4

from sqlalchemy import and_, func, or_, select, text, union_all, update
from sqlalchemy.exc import DBAPIError

from database.models import Article, ArticleVersion, AnnotationRun, AutomatedAnnotation
class AnnotationLockLost(RuntimeError):
    """The runner must stop writing if its dedicated lock connection is lost."""


class AnnotationLease:
    def __init__(self, connection, backend_id):
        self.connection = connection
        self.backend_id = backend_id
        self.lost = False

    def check(self):
        try:
            backend_id, owns_lock = self.connection.execute(text("""
                SELECT pg_backend_pid(), EXISTS (
                    SELECT 1 FROM pg_locks
                    WHERE locktype = 'advisory' AND pid = pg_backend_pid() AND granted
                      AND mode = 'ExclusiveLock' AND objsubid = 1
                      AND database = (SELECT oid FROM pg_database WHERE datname = current_database())
                      AND classid = ((hashtextextended(:name, 0) >> 32) & 4294967295)::oid
                      AND objid = (hashtextextended(:name, 0) & 4294967295)::oid
                )
            """), {"name": "automated-annotation-pipeline"}).one()
        except DBAPIError as exc:
            self.lost = True
            self.connection.invalidate()
            raise AnnotationLockLost("Annotation lock connection was lost") from exc
        if backend_id != self.backend_id or not owns_lock:
            self.lost = True
            raise AnnotationLockLost("Annotation lock backend or ownership changed")


def current_annotations(methods):
    """Latest compatible outputs, with L1 linked to the current valid L0 decision."""
    l0_ranked = select(
        AutomatedAnnotation.id, AutomatedAnnotation.article_version_id, AutomatedAnnotation.label,
        func.row_number().over(
            partition_by=AutomatedAnnotation.article_version_id,
            order_by=(AutomatedAnnotation.created_at.desc(), AutomatedAnnotation.id.desc()),
        ).label("position"),
    ).where(AutomatedAnnotation.layer == "L0", AutomatedAnnotation.method_version == methods["L0"]).subquery()
    l0 = select(l0_ranked.c.id, l0_ranked.c.article_version_id, l0_ranked.c.label).where(
        l0_ranked.c.position == 1
    ).subquery()
    # Filter L1 dependencies before ranking. A newer result for a custom L0
    # method must not hide an older result tied to the current default L0.
    ranked = select(
        AutomatedAnnotation,
        func.row_number().over(
            partition_by=(AutomatedAnnotation.article_version_id, AutomatedAnnotation.layer),
            order_by=(AutomatedAnnotation.created_at.desc(), AutomatedAnnotation.id.desc()),
        ).label("position"),
    ).outerjoin(l0, l0.c.article_version_id == AutomatedAnnotation.article_version_id).where(
        or_(and_(AutomatedAnnotation.layer == "L0", AutomatedAnnotation.method_version == methods["L0"]),
            and_(AutomatedAnnotation.layer == "L1", AutomatedAnnotation.method_version == methods["L1"],
                 AutomatedAnnotation.method_name == methods["L1_method_name"] if methods.get("L1_method_name") else True,
                 l0.c.label == "valid", AutomatedAnnotation.prerequisite_annotation_id == l0.c.id)),
    ).subquery()
    upstream = select(ranked).where(ranked.c.position == 1).subquery()
    if "L2" not in methods:
        return upstream
    # Match identity AND current dependency before ranking. Bootstrap rows and
    # newer incompatible predictions must never hide a compatible model result.
    l1 = select(upstream.c.id, upstream.c.article_version_id).where(
        upstream.c.layer == "L1", upstream.c.label == "kenya").subquery()
    l2_ranked = select(AutomatedAnnotation, func.row_number().over(
        partition_by=AutomatedAnnotation.article_version_id,
        order_by=(AutomatedAnnotation.created_at.desc(), AutomatedAnnotation.id.desc()),
    ).label("position")).join(l1, and_(
        l1.c.article_version_id == AutomatedAnnotation.article_version_id,
        l1.c.id == AutomatedAnnotation.prerequisite_annotation_id,
    )).where(AutomatedAnnotation.layer == "L2",
             AutomatedAnnotation.method_name == methods["L2_method_name"],
             AutomatedAnnotation.method_version == methods["L2"]).subquery()
    return union_all(select(upstream), select(l2_ranked).where(l2_ranked.c.position == 1)).subquery()


class AnnotationRepository:
    def __init__(self, sessions):
        self.sessions = sessions

    @contextmanager
    def lock(self):
        # Session-level lock, kept outside an idle transaction. A live heartbeat
        # before each write prevents continuing after a dropped lock connection.
        engine = self.sessions.kw["bind"]
        if "pooler" in (engine.url.host or "") and engine.url.port == 6543:
            raise RuntimeError("Annotations require a direct connection or session pooler, not transaction pooling")
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            parameters = {"name": "automated-annotation-pipeline"}
            acquired, backend_id = connection.execute(
                text("SELECT pg_try_advisory_lock(hashtextextended(:name, 0)), pg_backend_pid()"), parameters,
            ).one()
            if not acquired:
                raise RuntimeError("Another annotation run is already active")
            lease = AnnotationLease(connection, backend_id)
            try:
                yield lease
            finally:
                try:
                    if not lease.lost:
                        connection.execute(
                            text("SELECT pg_advisory_unlock(hashtextextended(:name, 0))"), parameters,
                        )
                except DBAPIError as exc:
                    # A lost physical session has already released its lock.
                    # Do not turn successfully checkpointed results into a CLI failure.
                    connection.invalidate()
                    logging.getLogger("annotations.service").warning(
                        "annotation_lock_release_failed error_type=%s", type(exc).__name__,
                    )

    def ensure_l2_schema(self):
        """Refuse any L2 run before run/result writes when its schema is incomplete."""
        from annotations.l2_readiness import l2_schema_readiness
        state = l2_schema_readiness(self.sessions)
        if not state["ready_for_prediction_writes"]:
            raise RuntimeError("L2 schema is not ready: " + ", ".join(state["missing"]))

    def create_run(self, layers, methods, trigger, collection_run_id, configuration):
        run_id = uuid4()
        with self.sessions.begin() as session:
            session.add(AnnotationRun(id=run_id, requested_layers=layers, method_versions=methods,
                                      trigger_type=trigger, collection_run_id=collection_run_id,
                                      configuration=configuration, status="running"))
        return run_id

    def select_candidates(self, layers, methods, limit=None, article_ids=None,
                          collection_run_id=None, only_pending=True, eligible_l2_only=False):
        statement = select(ArticleVersion, Article).join(Article, Article.id == ArticleVersion.article_id)
        if article_ids:
            statement = statement.where(Article.id.in_(article_ids))
        if collection_run_id:
            statement = statement.where(ArticleVersion.collection_run_id == collection_run_id)
        if eligible_l2_only:
            current = current_annotations(methods)
            statement = statement.where(select(current.c.id).where(
                current.c.article_version_id == ArticleVersion.id,
                current.c.layer == "L1", current.c.label == "kenya").exists())
        if only_pending:
            current = current_annotations(methods)
            l0 = select(current.c.id).where(current.c.article_version_id == ArticleVersion.id,
                                           current.c.layer == "L0").exists()
            valid_l0 = select(current.c.id).where(current.c.article_version_id == ArticleVersion.id,
                                                 current.c.layer == "L0", current.c.label == "valid").exists()
            l1 = select(current.c.id).where(current.c.article_version_id == ArticleVersion.id,
                                           current.c.layer == "L1").exists()
            conditions = []
            if "L0" in layers: conditions.append(~l0)
            if "L1" in layers: conditions.append(and_(valid_l0, ~l1) if "L0" in layers else ~l1)
            if "L2" in layers:
                l2 = select(current.c.id).where(current.c.article_version_id == ArticleVersion.id,
                                               current.c.layer == "L2").exists()
                conditions.append(~l2)
            statement = statement.where(or_(*conditions))
        statement = statement.order_by(ArticleVersion.created_at, ArticleVersion.id)
        if limit is not None: statement = statement.limit(limit)
        with self.sessions() as session:
            rows = session.execute(statement).all()
        candidates = []
        for version, article in rows:
            metadata = {field: getattr(article, field) for field in (
                "source", "canonical_url", "title", "published_at", "published_at_raw",
                "publication_date_needs_review", "content_scope",
            )}
            candidates.append({"id": version.id, "article_id": article.id, "metadata": metadata,
                               "raw_object_uri": version.raw_object_uri,
                               "processed_object_uri": version.processed_object_uri,
                               "processed_object_generation": version.processed_object_generation,
                               "content_hash": version.content_hash, "parser_version": version.parser_version})
        return candidates

    def set_selection(self, run_id, candidates):
        with self.sessions.begin() as session:
            run = session.get(AnnotationRun, run_id)
            configuration = dict(run.configuration)
            configuration["article_version_ids"] = [str(item["id"]) for item in candidates]
            run.configuration = configuration
            run.requested_count = len(candidates)

    def latest(self, version_id, layer, method_version, prerequisite_id=None, method_name=None):
        query = select(AutomatedAnnotation).where(
            AutomatedAnnotation.article_version_id == version_id,
            AutomatedAnnotation.layer == layer, AutomatedAnnotation.method_version == method_version,
        )
        if layer in ("L1", "L2"):
            query = query.where(AutomatedAnnotation.prerequisite_annotation_id == prerequisite_id)
        if layer == "L2" and not method_name:
            raise ValueError("L2 lookup requires explicit method_name")
        if method_name:
            query = query.where(AutomatedAnnotation.method_name == method_name)
        with self.sessions() as session:
            return session.scalars(query.order_by(AutomatedAnnotation.created_at.desc(),
                                                  AutomatedAnnotation.id.desc()).limit(1)).first()

    def current_for_candidates(self, version_ids, methods):
        """Read compatible gate/results once for the selected, locked run cohort."""
        if not version_ids:
            return {}
        current = current_annotations(methods)
        query = select(AutomatedAnnotation).where(
            AutomatedAnnotation.article_version_id.in_(version_ids),
            AutomatedAnnotation.id.in_(select(current.c.id)),
        )
        with self.sessions() as session:
            rows = session.scalars(query).all()
        return {(row.article_version_id, row.layer): row for row in rows}

    def protected_membership(self):
        """Shared automatic exclusions; incomplete validation schema fails closed."""
        from database.repositories.validation_batches import ValidationBatchRepository
        return ValidationBatchRepository(self.sessions).protected_membership()

    def reference_content_hashes(self, article_ids, article_version_ids):
        """Protect reference bodies including historical/out-of-cohort versions."""
        from uuid import UUID
        conditions = []
        if article_ids:
            conditions.append(ArticleVersion.article_id.in_([UUID(value) for value in article_ids]))
        if article_version_ids:
            conditions.append(ArticleVersion.id.in_([UUID(value) for value in article_version_ids]))
        if not conditions:
            return set()
        with self.sessions() as session:
            return set(session.scalars(select(ArticleVersion.content_hash).where(or_(*conditions))))

    def persist(self, candidate, run_id, result, prerequisite_id=None):
        row = AutomatedAnnotation(id=uuid4(), article_id=candidate["article_id"],
                                  article_version_id=candidate["id"], annotation_run_id=run_id,
                                  prerequisite_annotation_id=prerequisite_id,
                                  layer=result.layer, label=result.label, confidence=result.confidence,
                                  evidence=result.evidence, reason_codes=result.reason_codes,
                                  method_name=result.method_name, method_version=result.method_version)
        with self.sessions.begin() as session: session.add(row)
        return row

    def checkpoint(self, run_id, summary, status="running"):
        with self.sessions.begin() as session:
            session.execute(update(AnnotationRun).where(AnnotationRun.id == run_id).values(
                status=status, requested_count=summary["requested"], processed_count=summary["processed"],
                success_count=summary["success"], failed_count=summary["failed"], skipped_count=summary["skipped"],
                summary=summary, error_summary={"errors": summary["errors"]} if summary["errors"] else None,
                completed_at=None if status == "running" else datetime.now(timezone.utc),
            ))
