"""Append-only human review and deterministic current/cohort queries."""
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from uuid import UUID, uuid4

from sqlalchemy import case, func, inspect, select
from sqlalchemy.exc import IntegrityError

from annotations.schemas import DEFAULT_CONFIG
from annotations.validation import ReviewConflict, STATUSES, validate_review
from database.models import Article, ArticleVersion, AutomatedAnnotation, HumanValidation
from database.repositories.annotations import current_annotations


def latest_validations():
    ranked = select(HumanValidation, func.row_number().over(
        partition_by=HumanValidation.automated_annotation_id,
        order_by=(HumanValidation.created_at.desc(), HumanValidation.id.desc()),
    ).label("position")).subquery()
    return select(ranked).where(ranked.c.position == 1).subquery()


def reviewed_results(current, available, label_basis="effective"):
    """Overlay latest L2 reviews without mutating machine rows or eligibility.

    Resolved reviews supply their label; unresolved reviews remain borderline.
    Without review storage, inspection falls back to machine labels.
    """
    if not available or label_basis == "machine":
        return select(current, current.c.label.label("result_label")).subquery()
    latest = latest_validations()
    label = case(
        (latest.c.review_decision.in_(("confirmed", "corrected")), latest.c.human_label),
        (latest.c.review_decision.in_(("unable_to_determine", "needs_adjudication")), "borderline"),
        else_=current.c.label,
    )
    return select(current, label.label("result_label")).outerjoin(
        latest, latest.c.automated_annotation_id == current.c.id).subquery()


def method_versions():
    return {layer: DEFAULT_CONFIG.method_version(layer) for layer in ("L0", "L1")}


class HumanValidationRepository:
    def __init__(self, sessions):
        self.sessions = sessions

    @lru_cache(maxsize=1)
    def available(self):
        """Migration readiness, cached until app restart after schema installation."""
        return inspect(self.sessions.kw["bind"]).has_table("human_validations", schema="public")

    @lru_cache(maxsize=1)
    def l2_available(self):
        """Require all three extended constraints, not merely an existing review table."""
        if not self.available():
            return False
        constraints = inspect(self.sessions.kw["bind"]).get_check_constraints("human_validations", schema="public")
        names = {"human_validation_layer_check", "human_validation_machine_label_check",
                 "human_validation_label_check"}
        return names <= {row["name"] for row in constraints if "'L2'" in row["sqltext"]}

    def detail(self, annotation_id):
        query = select(AutomatedAnnotation, Article, ArticleVersion).join(
            Article, Article.id == AutomatedAnnotation.article_id).join(
            ArticleVersion, ArticleVersion.id == AutomatedAnnotation.article_version_id).where(
                AutomatedAnnotation.id == annotation_id, ArticleVersion.article_id == Article.id,
                AutomatedAnnotation.layer.in_(("L0", "L1", "L2")))
        with self.sessions() as session:
            row = session.execute(query).first()
        if row is None:
            return None
        return {"annotation": row[0], "article": row[1], "version": row[2]}

    def history(self, annotation_id):
        if not self.available():
            return None
        with self.sessions() as session:
            return session.scalars(select(HumanValidation).where(
                HumanValidation.automated_annotation_id == annotation_id).order_by(
                    HumanValidation.created_at.desc(), HumanValidation.id.desc())).all()

    def statuses(self, annotation_ids):
        if not self.available():
            return None
        if not annotation_ids:
            return {}
        latest = latest_validations()
        with self.sessions() as session:
            rows = session.execute(select(latest.c.automated_annotation_id, latest.c.review_decision).where(
                latest.c.automated_annotation_id.in_(annotation_ids))).all()
        return dict(rows)

    def latest_for_annotations(self, annotation_ids):
        """Read exact latest review lineage/labels in one query, without private notes."""
        if not self.l2_available():
            raise RuntimeError("L2 human-validation schema is required for reviewed export")
        if not annotation_ids:
            return {}
        latest = latest_validations()
        fields = ("id", "automated_annotation_id", "article_id", "article_version_id", "layer",
                  "machine_label", "human_label", "review_decision", "guideline_version", "created_at")
        with self.sessions() as session:
            rows = session.execute(select(*(latest.c[key] for key in fields)).where(
                latest.c.automated_annotation_id.in_(annotation_ids))).mappings().all()
        return {row["automated_annotation_id"]: dict(row) for row in rows}

    def summary(self, current, layers=("L0", "L1")):
        if not self.available() or ("L2" in layers and not self.l2_available()):
            return None
        latest = latest_validations()
        with self.sessions() as session:
            rows = session.execute(select(current.c.layer, current.c.label, latest.c.review_decision,
                func.count()).outerjoin(latest, latest.c.automated_annotation_id == current.c.id).where(
                    current.c.layer.in_(layers)).group_by(
                    current.c.layer, current.c.label, latest.c.review_decision)).all()
        totals = {layer: {status: 0 for status in STATUSES} for layer in layers}
        priority = {"L0": "needs_review", "L1": "ambiguous", "L2": "borderline"}
        progress = {layer: {"label": priority[layer], "reviewed": 0, "total": 0} for layer in layers}
        for layer, label, decision, count in rows:
            totals[layer][decision or "not_reviewed"] += count
            if label == progress[layer]["label"]:
                progress[layer]["total"] += count
                if decision:
                    progress[layer]["reviewed"] += count
        for values in totals.values():
            values["reviewed"] = sum(values[k] for k in STATUSES if k != "not_reviewed")
        return {"counts": totals, "progress": progress}

    def neighbors(self, annotation, filters, per_page, methods=None):
        """Compute navigation inside the same method/layer/label/source cohort."""
        methods = methods or method_versions()
        current = current_annotations(methods)
        if annotation.layer == "L2":
            current = reviewed_results(current, self.l2_available(), filters.get("label_basis", "effective"))
        conditions = [current.c.layer == annotation.layer]
        if filters.get("label"):
            conditions.append((current.c.result_label if annotation.layer == "L2" else current.c.label) == filters["label"])
        if filters.get("source"):
            conditions.append(Article.source == filters["source"])
        if annotation.layer == "L2":
            if filters.get("method_version"):
                conditions.append(current.c.method_version == filters["method_version"])
            if filters.get("model_version"):
                conditions.append(current.c.evidence["model_version"].as_string() == filters["model_version"])
        latest = None
        if filters.get("review_status") and self.available():
            latest = latest_validations()
            conditions.append(latest.c.review_decision.is_(None) if filters["review_status"] == "not_reviewed"
                              else latest.c.review_decision.is_not(None) if filters["review_status"] == "reviewed"
                              else latest.c.review_decision == filters["review_status"])
        order = (current.c.created_at.desc(), current.c.id.desc())
        cohort = select(current.c.id,
            func.lag(current.c.id).over(order_by=order).label("previous_id"),
            func.lead(current.c.id).over(order_by=order).label("next_id"),
            func.row_number().over(order_by=order).label("position"),
            func.count().over().label("total"),
        ).join(Article, Article.id == current.c.article_id)
        if latest is not None:
            cohort = cohort.outerjoin(latest, latest.c.automated_annotation_id == current.c.id)
        cohort = cohort.where(*conditions).subquery()
        with self.sessions() as session:
            row = session.execute(select(cohort).where(cohort.c.id == annotation.id)).mappings().first()
        if row is None:
            return {"previous_id": None, "next_id": None, "position": None, "total": None}
        result = dict(row)
        for key in ("previous_id", "next_id"):
            if result[key] is not None:
                result[key] = UUID(str(result[key]))
        result["previous_page"] = max(1, (row["position"] - 2) // per_page + 1)
        result["next_page"] = (row["position"]) // per_page + 1
        return result

    def create(self, annotation_id, values, reviewer_identity, guideline_version, expected_current_id):
        if not self.available():
            raise RuntimeError("Human-validation migration is not installed")
        if not reviewer_identity.strip() or not guideline_version.strip():
            raise ValueError("Configured reviewer identity and guideline version are required")
        expected = UUID(str(expected_current_id)) if expected_current_id else None
        try:
            with self.sessions.begin() as session:
                # Serialize revisions without modifying the locked machine row.
                annotation = session.scalar(select(AutomatedAnnotation).where(
                    AutomatedAnnotation.id == annotation_id).with_for_update())
                if annotation is None:
                    raise LookupError("Annotation not found")
                if annotation.layer == "L2" and not self.l2_available():
                    raise RuntimeError("L2 human-validation migration is not installed")
                fields = validate_review(annotation, **values)
                current = session.scalar(select(HumanValidation).where(
                    HumanValidation.automated_annotation_id == annotation_id).order_by(
                        HumanValidation.created_at.desc(), HumanValidation.id.desc()).limit(1))
                if (current.id if current else None) != expected:
                    raise ReviewConflict("Another review was saved. Reload and inspect its history before revising.")
                now = datetime.now(timezone.utc)
                if current and now <= current.created_at.replace(tzinfo=timezone.utc):
                    now = current.created_at.replace(tzinfo=timezone.utc) + timedelta(microseconds=1)
                review = HumanValidation(id=uuid4(), automated_annotation_id=annotation.id,
                    article_id=annotation.article_id, article_version_id=annotation.article_version_id,
                    layer=annotation.layer, machine_label=annotation.label, machine_confidence=annotation.confidence,
                    reviewer_identity=reviewer_identity.strip(), guideline_version=guideline_version.strip(),
                    created_at=now, supersedes_validation_id=current.id if current else None, **fields)
                session.add(review)
            return review
        except IntegrityError as exc:
            # Another form may have raced the initial/next review insert.
            raise ReviewConflict("Review history changed. Reload before saving.") from exc
