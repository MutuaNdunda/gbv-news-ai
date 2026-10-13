"""Separate researcher capability, private localhost access and sealed blind review."""
import hashlib
import hmac
import time

from flask import Blueprint, abort, current_app, request, session, redirect, send_file
from sqlalchemy.exc import SQLAlchemyError

from app.security import local_review_request, csrf_token, require_csrf, review_enabled
from app.routes.validation import repository, private_response, private_json, access as review_access
from app.services.model_performance_service import ModelPerformanceService, curve_points
from annotations.reference_quality import blinded_audit_sample

blueprint = Blueprint('model_performance', __name__, url_prefix='/annotations/model-performance')
CSRF = 'model_performance_csrf'


def performance_access():
    config = current_app.config; token = config.get('MODEL_PERFORMANCE_TOKEN') or ''
    if (not config.get('MODEL_PERFORMANCE_ENABLED') or len(token) < 32 or not review_enabled()
        or not local_review_request() or hmac.compare_digest(token, config.get('HUMAN_REVIEW_TOKEN') or '')):
        abort(403)
    binding = hashlib.sha256((token + current_app.config['HUMAN_REVIEW_GUIDELINE_VERSION']).encode()).hexdigest()
    if request.method == 'POST':
        require_csrf(CSRF)
        if request.form.get('action') != 'unlock': abort(400)
        if not hmac.compare_digest((request.form.get('performance_token') or '').encode(), token.encode()): abort(403)
        session['performance_binding'] = binding; session['performance_started'] = time.time()
        return redirect(request.full_path.rstrip('?'), code=303)
    elapsed = time.time()-session.get('performance_started', 0)
    if not (0 <= elapsed < 1800 and hmac.compare_digest(session.get('performance_binding',''), binding)):
        return private_response('annotations/performance_unlock.html', csrf=csrf_token(CSRF))
    return None


def service():
    return ModelPerformanceService(repository(), current_app.config['MODEL_PERFORMANCE_REPORT_ROOT'])


@blueprint.after_request
def protect_response(response):
    response.headers.update({'Cache-Control':'private, no-store','Referrer-Policy':'no-referrer',
        'X-Frame-Options':'DENY','X-Content-Type-Options':'nosniff','X-Robots-Tag':'noindex, noarchive'})
    return response


@blueprint.route('', methods=['GET','POST'])
def index():
    locked = performance_access()
    if locked is not None: return locked
    batches=[]; data=None; bundle=None; error=None; status=200
    try:
        svc=service(); batches=svc.repository.list()
        selected=request.args.get('batch') or (str(batches[0].id) if batches else None)
        if selected:
            data=svc.repository.reference_audit(selected)
            data.pop('audit_candidates')
            if data['status']=='completed':
                try: bundle=svc.bundle(selected)
                except (LookupError, ValueError) as exc: error=str(exc)
    except LookupError: abort(404)
    except (RuntimeError, ValueError, OSError) as exc: error=str(exc); status=503
    except SQLAlchemyError: error='Private validation storage is unavailable.'; status=503
    response=private_response('annotations/model_performance.html', batches=batches, audit=data,
        bundle=bundle, report=bundle['report'] if bundle else None, error=error, curve_points=curve_points)
    response.status_code=status
    return response


@blueprint.get('/<uuid:batch_id>/errors')
def errors(batch_id):
    locked=performance_access()
    if locked is not None: return locked
    try:
        svc=service(); bundle=svc.bundle(batch_id)
        data=svc.records(bundle, request.args, request.args.get('page',1))
    except LookupError: abort(404)
    except (ValueError, RuntimeError, OSError): abort(409, description='Private evaluation unavailable or comparisons blocked. Return to Model Performance for readiness.')
    except SQLAlchemyError: abort(503)
    return private_response('annotations/performance_errors.html', batch_id=batch_id, bundle=bundle,
        filters=request.args, **data)


@blueprint.get('/<uuid:batch_id>/errors/<uuid:member_id>/body')
def body(batch_id, member_id):
    locked=performance_access()
    if locked is not None: return locked
    try:
        svc=service(); bundle=svc.bundle(batch_id)
        if not any(r['member_id']==str(member_id) for r in bundle['pairs']): abort(404)
        record=svc.repository.bulk_content_record(batch_id, member_id)
        if not record['version'].processed_object_generation:
            return private_json({'article_text':None, 'content_issue':'This legacy extraction has no pinned object generation; private diagnostic body access is withheld.'},409)
        content=current_app.extensions['monitor_services']['annotations'].review_content(record)
        return private_json({'article_text':content.get('article_text'), 'content_issue':content.get('content_issue')})
    except LookupError: abort(404)
    except (ValueError, RuntimeError, OSError): abort(409)
    except SQLAlchemyError: abort(503)


@blueprint.get('/<uuid:batch_id>/export/<name>')
def export(batch_id, name):
    locked=performance_access()
    if locked is not None: return locked
    allowed={'evaluation_report.json','manifest.json','invocation.json','invocation_manifest.json',
             'classification.csv','confusion_matrix.csv','subgroups.csv','errors.csv'}
    if name not in allowed: abort(404)
    try:
        bundle=service().bundle(batch_id)
        if name not in ('manifest.json','invocation.json','invocation_manifest.json') and name not in bundle['manifest']['files_sha256']: abort(404)
        return send_file(bundle['directory']/name, as_attachment=True, download_name=name, conditional=False)
    except LookupError: abort(404)
    except (ValueError, RuntimeError, OSError): abort(409)
    except SQLAlchemyError: abort(503)


@blueprint.get('/<uuid:batch_id>/reference-audit')
def reference_audit(batch_id):
    # This view belongs to the blinded review capability. It never loads reports.
    locked=review_access()
    if locked is not None: return locked
    try:
        data=repository().reference_audit(batch_id)
        sample=blinded_audit_sample(data['audit_candidates'])
        evidence_filter=request.args.get('evidence','title_only')
        if evidence_filter not in ('all','title_only','verified_body_access','other_unknown','proposed_sample'): abort(400)
        rows=sample if evidence_filter=='proposed_sample' else [r for r in data['audit_candidates']
            if evidence_filter=='all' or r['evidence_basis']==evidence_filter]
        page=max(1, request.args.get('page',1,type=int)); total=len(rows); last=max(1,(total+24)//25); page=min(page,last)
        rows=rows[(page-1)*25:page*25]
        # Sampling strata use accepted human labels internally; blind packet masks them.
        for row in rows: row.pop('human_label',None)
        data.pop('audit_candidates')
    except LookupError: abort(404)
    except (RuntimeError, ValueError): abort(409)
    except SQLAlchemyError: abort(503)
    return private_response('annotations/reference_audit.html', audit=data, rows=rows, evidence_filter=evidence_filter,
        page=page, last_page=last, total=total, sample_size=len(sample), batch_id=batch_id)
