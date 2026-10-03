"""Read-only monitor queries and a thin bridge to the shared annotation runner."""

from sqlalchemy import func, select

from annotations.schemas import DEFAULT_CONFIG
from annotations.service import run_annotation_pipeline
from database.models import AnnotationRun, Article, ArticleVersion, AutomatedAnnotation
from database.repositories.annotations import current_annotations


class AnnotationService:
    def __init__(self, sessions, objects):
        self.sessions, self.objects = sessions, objects

    def current(self):
        return current_annotations({layer: DEFAULT_CONFIG.method_version(layer) for layer in ("L0", "L1")})

    def overview(self):
        current = self.current()
        with self.sessions() as session:
            total = session.scalar(select(func.count()).select_from(ArticleVersion))
            breakdown = session.execute(select(current.c.layer, current.c.label, func.count()).group_by(
                current.c.layer, current.c.label)).all()
            recent = session.scalars(select(AnnotationRun).order_by(AnnotationRun.started_at.desc()).limit(10)).all()
        counts = {"L0": {"valid": 0, "needs_review": 0, "invalid": 0},
                  "L1": {"kenya": 0, "not_kenya": 0, "ambiguous": 0}}
        for layer, label, count in breakdown: counts[layer][label] = count
        return {"total_versions": total, "counts": counts, "recent_runs": recent,
                "pending_l0": total - sum(counts["L0"].values()),
                "pending_l1": counts["L0"]["valid"] - sum(counts["L1"].values())}

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
        current = self.current()
        query = select(AutomatedAnnotation, Article).join(Article, Article.id == AutomatedAnnotation.article_id).where(
            AutomatedAnnotation.id.in_(select(current.c.id)), AutomatedAnnotation.layer == layer)
        if filters.get("label"): query = query.where(AutomatedAnnotation.label == filters["label"])
        if filters.get("source"): query = query.where(Article.source == filters["source"])
        with self.sessions() as session:
            total = session.scalar(select(func.count()).select_from(query.subquery()))
            rows = session.execute(query.order_by(AutomatedAnnotation.created_at.desc(), AutomatedAnnotation.id.desc()).offset(
                (page - 1) * per_page).limit(per_page)).all()
        return rows, total

    def article_results(self, article_id):
        with self.sessions() as session:
            return session.scalars(select(AutomatedAnnotation).where(
                AutomatedAnnotation.article_id == article_id).order_by(
                AutomatedAnnotation.created_at.desc(), AutomatedAnnotation.id.desc()).limit(200)).all()

    def run(self, layers, limit):
        from database.repositories.annotations import AnnotationRepository
        return run_annotation_pipeline(layers, limit=limit, trigger_type="manual_ui",
                                       services=(AnnotationRepository(self.sessions), self.objects))
