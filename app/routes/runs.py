"""Collection monitor and opt-in cooperative cancellation (no execution/kill API)."""
import hmac
from uuid import UUID

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import SQLAlchemyError

from app.security import csrf_token, require_csrf
from app.services.run_service import run_liveness
from database.repositories.collection_runs import RUN_STATUSES

blueprint = Blueprint('runs', __name__, url_prefix='/runs')


def control_enabled():
    return (current_app.config.get('COLLECTION_CONTROL_ENABLED', False)
            and len(current_app.config.get('COLLECTION_CONTROL_TOKEN') or '') >= 32
            and len(current_app.secret_key or '') >= 32)


def render_page(template, **data):
    enabled = control_enabled()
    response = current_app.make_response(render_template(template, **data,
        status_options=RUN_STATUSES, control_enabled=enabled,
        csrf=csrf_token('collection_csrf') if enabled else None))
    if enabled:
        response.headers.update({'Cache-Control': 'private, no-store', 'Referrer-Policy': 'no-referrer',
                                 'X-Frame-Options': 'DENY'})
    return response


@blueprint.get('')
def index():
    page = max(request.args.get('page', 1, type=int), 1)
    status = request.args.get('status', '').strip()
    if status not in RUN_STATUSES:
        status = ''
    per_page = current_app.config['PER_PAGE']
    service = current_app.extensions['monitor_services']['runs']
    rows, total = service.list(page, per_page, status=status)
    # Bound out-of-range pages after a cohort shrinks; links retain the filter.
    last_page = max(1, (total + per_page - 1) // per_page)
    if page > last_page:
        return redirect(url_for('runs.index', status=status, page=last_page))
    states = {run.id: run_liveness(run, current_app.config['COLLECTION_STALE_SECONDS'])
              for run, *_ in rows}
    return render_page('runs/index.html', rows=rows, page=page, total=total,
                       status=status, states=states, last_page=last_page)


@blueprint.get('/<uuid:run_id>')
def detail(run_id: UUID):
    data = current_app.extensions['monitor_services']['runs'].detail(run_id)
    if data is None:
        abort(404)
    return render_page('runs/detail.html', **data,
                       state=run_liveness(data['run'], current_app.config['COLLECTION_STALE_SECONDS']))


@blueprint.post('/<uuid:run_id>/stop')
def stop(run_id):
    if not control_enabled():
        abort(403)
    if not request.is_secure and request.remote_addr not in ('127.0.0.1', '::1'):
        abort(403)
    supplied = request.form.get('execution_token', '')
    if not hmac.compare_digest(supplied.encode(), current_app.config['COLLECTION_CONTROL_TOKEN'].encode()):
        abort(403)
    require_csrf('collection_csrf')
    try:
        result = current_app.extensions['monitor_services']['runs'].request_stop(run_id)
    except SQLAlchemyError as exc:
        current_app.logger.warning('collection_stop_failed error_type=%s', type(exc).__name__)
        flash('Stop request could not be saved. Check database connectivity and the collection-control migration.', 'warning')
    else:
        if result == 'missing':
            abort(404)
        messages = {'requested': 'Stop requested. The worker will checkpoint and stop at a safe boundary.',
                    'already_requested': 'Stop has already been requested. Waiting for the worker.',
                    'inactive': 'This run has ended. Its history was preserved.',
                    'unavailable': 'Install the collection-control migration and restart the app before enabling Stop Run.',
                    'unsupported': 'This worker predates cooperative control. No stop request was written; use its original terminal session to interrupt it.'}
        flash(messages[result], 'info')
    return redirect(url_for('runs.detail', run_id=run_id), code=303)
