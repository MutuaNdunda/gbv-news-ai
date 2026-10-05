"""Read-only monitor queries and a thin bridge to the shared annotation runner."""

import hashlib
from urllib.parse import urlsplit

from sqlalchemy import func, select

from annotations.schemas import DEFAULT_CONFIG
from annotations.l2 import current_l2_methods
from annotations.l2_training import bootstrap_methods
from annotations.service import load_article, run_annotation_pipeline
from database.models import AnnotationRun, Article, ArticleVersion, AutomatedAnnotation
from database.repositories.annotations import current_annotations
from database.repositories.human_validations import HumanValidationRepository, latest_validations, method_versions


class AnnotationService:
    def __init__(self, sessions, objects):
        self.sessions, self.objects = sessions, objects
        self.reviews = HumanValidationRepository(sessions)

    def methods(self, mode="model"):
        if mode == "weak":
            return bootstrap_methods()
        methods = {layer: DEFAULT_CONFIG.method_version(layer) for layer in ("L0", "L1")}
        try:
            methods.update(current_l2_methods())
        except ValueError:
            # L2 readiness must not make existing L0/L1 inspection unavailable.
            methods.update(L2="l2-model-unavailable", L2_method_name="afroxlmr_gbv_relevance")
        return methods

    def current(self, mode="model"):
        return current_annotations(self.methods(mode))

    def overview(self):
        current = self.current()
        with self.sessions() as session:
            total = session.scalar(select(func.count()).select_from(ArticleVersion))
            breakdown = session.execute(select(current.c.layer, current.c.label, func.count()).group_by(
                current.c.layer, current.c.label)).all()
            recent = session.scalars(select(AnnotationRun).order_by(AnnotationRun.started_at.desc()).limit(10)).all()
        counts = {"L0": {"valid": 0, "needs_review": 0, "invalid": 0},
                  "L1": {"kenya": 0, "not_kenya": 0, "ambiguous": 0},
                  "L2": {"gbv": 0, "not_gbv": 0, "borderline": 0}}
        for layer, label, count in breakdown: counts[layer][label] = count
        return {"total_versions": total, "counts": counts, "recent_runs": recent,
                "pending_l0": total - sum(counts["L0"].values()),
                "pending_l1": counts["L0"]["valid"] - sum(counts["L1"].values()),
                "eligible_l2": counts["L1"]["kenya"],
                "l2_model_ready": self.methods()["L2"] not in ("l2-model-unavailable", "l2-model-unconfigured"),
                "pending_l2": counts["L1"]["kenya"] - sum(counts["L2"].values()),
                "methods": self.methods(), "human_review": self.reviews.summary(
                    current_annotations(method_versions())),
                "l2_human_review": {mode: self.reviews.summary(self.current(mode), layers=("L2",))
                                    for mode in ("weak", "model")}}

    def runs(self, page, per_page):
        with self.sessions() as session:
            total = session.scalar(select(func.count()).select_from(AnnotationRun))
            rows = session.scalars(select(AnnotationRun).order_by(AnnotationRun.started_at.desc()).offset(
                (page - 1) * per_page).limit(per_page)).all()
        return rows, total

    def run_detail(self, run_id):
        with self.sessions() as session:
            run = session.get(AnnotationRun, run_id)
            if run is None: return None
            breakdown = session.execute(select(AutomatedAnnotation.layer, AutomatedAnnotation.label, func.count()).where(
                AutomatedAnnotation.annotation_run_id == run_id).group_by(
                AutomatedAnnotation.layer, AutomatedAnnotation.label)).all()
        return {"run": run, "breakdown": breakdown}

    def results(self, layer, filters, page, per_page):
        current = self.current(filters.get("mode", "model"))
        query = select(AutomatedAnnotation, Article).join(Article, Article.id == AutomatedAnnotation.article_id).where(
            AutomatedAnnotation.id.in_(select(current.c.id)), AutomatedAnnotation.layer == layer)
        query = self.filter_review_status(query, AutomatedAnnotation.id, filters, layer)
        if filters.get("label"): query = query.where(AutomatedAnnotation.label == filters["label"])
        if filters.get("source"): query = query.where(Article.source == filters["source"])
        if layer == "L2":
            if filters.get("method_version"):
                query = query.where(AutomatedAnnotation.method_version == filters["method_version"])
            if filters.get("model_version"):
                query = query.where(AutomatedAnnotation.evidence["model_version"].as_string() == filters["model_version"])
        with self.sessions() as session:
            total = session.scalar(select(func.count()).select_from(query.subquery()))
            rows = session.execute(query.order_by(AutomatedAnnotation.created_at.desc(), AutomatedAnnotation.id.desc()).offset(
                (page - 1) * per_page).limit(per_page)).all()
        return rows, total

    def filter_review_status(self, query, annotation_id, filters, layer):
        if not filters.get("review_status"):
            return query
        if not self.reviews.available() or (layer == "L2" and not self.reviews.l2_available()):
            raise RuntimeError("Human-validation migration is not installed")
        latest = latest_validations()
        query = query.outerjoin(latest, latest.c.automated_annotation_id == annotation_id)
        return query.where(latest.c.review_decision.is_(None) if filters["review_status"] == "not_reviewed"
                          else latest.c.review_decision.is_not(None) if filters["review_status"] == "reviewed"
                          else latest.c.review_decision == filters["review_status"])

    def pending_l2(self, filters, page, per_page):
        current = self.current(filters.get("mode", "model"))
        done = select(current.c.article_version_id).where(current.c.layer == "L2")
        query = select(AutomatedAnnotation, Article).join(Article, Article.id == AutomatedAnnotation.article_id).where(
            AutomatedAnnotation.id.in_(select(current.c.id)), AutomatedAnnotation.layer == "L1",
            AutomatedAnnotation.label == "kenya", AutomatedAnnotation.article_version_id.not_in(done))
        if filters.get("source"):
            query = query.where(Article.source == filters["source"])
        with self.sessions() as session:
            total = session.scalar(select(func.count()).select_from(query.subquery()))
            rows = session.execute(query.order_by(AutomatedAnnotation.created_at.desc(), AutomatedAnnotation.id.desc()).offset(
                (page - 1) * per_page).limit(per_page)).all()
        return rows, total

    def l2_label_counts(self, filters):
        """Count compatible labels across pages, keeping source/version scope."""
        current = self.current(filters.get("mode", "model"))
        query = select(current.c.label, func.count()).join(
            Article, Article.id == current.c.article_id).where(current.c.layer == "L2")
        query = self.filter_review_status(query, current.c.id, filters, "L2")
        if filters.get("source"):
            query = query.where(Article.source == filters["source"])
        if filters.get("method_version"):
            query = query.where(current.c.method_version == filters["method_version"])
        if filters.get("model_version"):
            query = query.where(current.c.evidence["model_version"].as_string() == filters["model_version"])
        with self.sessions() as session:
            breakdown = session.execute(query.group_by(current.c.label)).all()
        counts = {"gbv": 0, "not_gbv": 0, "borderline": 0}
        counts.update(dict(breakdown))
        return counts

    def l2_detail(self, annotation_id):
        """Historical inspection and exact prerequisite metadata."""
        query = select(AutomatedAnnotation, Article, ArticleVersion).join(
            Article, Article.id == AutomatedAnnotation.article_id).join(
            ArticleVersion, ArticleVersion.id == AutomatedAnnotation.article_version_id).where(
            AutomatedAnnotation.id == annotation_id, AutomatedAnnotation.layer == "L2",
            ArticleVersion.article_id == Article.id)
        with self.sessions() as session:
            row = session.execute(query).first()
            if row is None:
                return None
            prerequisite = session.get(AutomatedAnnotation, row[0].prerequisite_annotation_id)
        return {"annotation": row[0], "article": row[1], "version": row[2], "prerequisite": prerequisite}

    def article_results(self, article_id):
        with self.sessions() as session:
            return session.scalars(select(AutomatedAnnotation).where(
                AutomatedAnnotation.article_id == article_id).order_by(
                AutomatedAnnotation.created_at.desc(), AutomatedAnnotation.id.desc()).limit(200)).all()

    def run(self, layers, limit):
        from database.repositories.annotations import AnnotationRepository
        return run_annotation_pipeline(layers, limit=limit, trigger_type="manual_ui",
                                       services=(AnnotationRepository(self.sessions), self.objects))


    def review_statuses(self, rows):
        if any(result.layer == "L2" for result, _ in rows) and not self.reviews.l2_available():
            return None
        return self.reviews.statuses([result.id for result, _ in rows])

    def review_record(self, annotation_id):
        return self.reviews.detail(annotation_id)

    def review_detail(self, annotation_id, filters, per_page):
        data = self.reviews.detail(annotation_id)
        if data is None:
            return None
        is_l2 = data["annotation"].layer == "L2"
        data["history"] = (None if is_l2 and not self.reviews.l2_available()
                           else self.reviews.history(annotation_id))
        data["current_review"] = data["history"][0] if data["history"] else None
        data["neighbors"] = self.reviews.neighbors(data["annotation"], filters, per_page,
            methods=self.methods(filters.get("mode") or "model") if is_l2 else None)
        if is_l2:
            with self.sessions() as session:
                data["prerequisite"] = session.get(AutomatedAnnotation, data["annotation"].prerequisite_annotation_id)
        try:
            url = urlsplit(data["article"].canonical_url)
        except ValueError:
            url = urlsplit("")
        data["canonical_link"] = (data["article"].canonical_url if url.scheme in ("http", "https")
                                  and url.netloc and not url.username and not url.password else None)
        return data

    def review_content(self, data):
        """Reuse generation-pinned loading; no storage reads happen in result lists."""
        article, version = data["article"], data["version"]
        candidate = {"metadata": {field: getattr(article, field) for field in (
            "source", "title", "canonical_url", "published_at", "published_at_raw",
            "publication_date_needs_review", "content_scope")},
            **{field: getattr(version, field) for field in ("raw_object_uri", "processed_object_uri",
                "processed_object_generation", "content_hash", "parser_version")}}
        try:
            record = load_article(candidate, self.objects)
        except Exception as exc:
            # Never propagate storage credentials/content in error messages or logs.
            import logging
            logging.getLogger(__name__).warning("review_content_unavailable error_type=%s", type(exc).__name__)
            return {"article_text": None, "content_issue": "Stored extraction is temporarily unavailable."}
        body = record.get("article_text")
        if record["processed_object_missing"]:
            return {"article_text": None, "content_issue": "The stored processed extraction is missing."}
        if record["lineage_errors"] or not isinstance(body, str) or hashlib.sha256(body.encode()).hexdigest() != version.content_hash.lower():
            return {"article_text": None, "content_issue": "The stored extraction cannot be verified against this article version."}
        return {"article_text": body, "content_issue": None, "content_article": record}

    def save_review(self, annotation_id, values, reviewer_identity, guideline_version, expected_current_id):
        return self.reviews.create(annotation_id, values, reviewer_identity, guideline_version, expected_current_id)
