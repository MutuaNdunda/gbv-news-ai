"""Read persisted private metrics; GET never evaluates, infers or changes references."""
from pathlib import Path

from annotations.evaluation_reports import REPORT_ROOT, load_bundle
from annotations.l2_training import ROOT


class ModelPerformanceService:
    def __init__(self, repository, report_root=REPORT_ROOT):
        self.repository = repository
        self.report_root = Path(report_root)
        if not self.report_root.is_absolute():
            self.report_root = ROOT / self.report_root
        if not self.report_root.resolve().is_relative_to(ROOT/'data'):
            raise ValueError('Performance reports must remain under private ignored data/.')

    def bundle(self, identifier):
        data = self.repository.detail(identifier); batch = data['batch']
        if batch.status != 'completed':
            raise ValueError('Evaluation pending — human reference batch has not been completed.')
        if self.repository.has_blinded_assignments():
            raise ValueError('Model comparisons are blocked while a blinded batch assignment is active.')
        # Final-test feedback requires a separately approved CLI release. No tuning UI.
        found = []
        for manifest in self.report_root.glob('*/manifest.json'):
            import json
            try:
                identity = json.loads(manifest.read_text())
            except (OSError, ValueError):
                continue
            if identity.get('batch_id') == str(batch.id):
                found.append(manifest)
        if not found:
            raise LookupError('No private evaluation report. Run the evaluator explicitly into a new private directory after reference acceptance.')
        newest = max(found, key=lambda p: (p.stat().st_mtime_ns, str(p)))
        return load_bundle(newest.parent, batch, data['members'], self.report_root)

    def records(self, bundle, filters, page=1):
        rows = bundle['pairs']
        for key in ('error_category', 'source', 'language', 'evidence_basis'):
            value = filters.get(key, '')
            if value:
                rows = [r for r in rows if (r.get(key) or 'unknown') == value]
        try:
            low, high = float(filters.get('min_probability') or 0), float(filters.get('max_probability') or 1)
            page = max(1, int(page))
        except (ValueError, TypeError):
            raise ValueError('Invalid page or probability range.')
        if not 0 <= low <= high <= 1:
            raise ValueError('Choose a probability range within 0–1.')
        rows = [r for r in rows if low <= r['gbv_probability'] <= high]
        last_page = max(1, (len(rows)+24)//25); page = min(page, last_page)
        selected = rows[(page-1)*25:page*25]
        # Metadata enrichment uses a single bounded SQL query, never the body reader.
        from sqlalchemy import select
        from uuid import UUID
        from database.models import Article
        with self.repository.sessions() as db:
            articles = {str(a.id): a for a in db.scalars(select(Article).where(
                Article.id.in_([UUID(r['article_id']) for r in selected])))}
        enriched = [dict(r, title=articles[r['article_id']].title if r['article_id'] in articles else 'Unavailable catalog headline',
            published_at=articles[r['article_id']].published_at if r['article_id'] in articles else None) for r in selected]
        return dict(rows=enriched, total=len(rows), page=page, last_page=last_page,
            options={k: sorted({r.get(k) or 'unknown' for r in bundle['pairs']})
                     for k in ('error_category','source','language','evidence_basis')})


def curve_points(points):
    """SVG presentation coordinates only; all scientific values come from reports."""
    return ' '.join(f'{40+320*x:.2f},{220-180*y:.2f}' for x,y in points)
