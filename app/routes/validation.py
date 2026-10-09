"""Protected validation operations inside the existing annotation/review workspace."""
import time
from uuid import UUID
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from sqlalchemy.exc import SQLAlchemyError

from app.security import csrf_token, local_review_request, require_csrf, review_authenticated, review_enabled, unlock_review
from annotations.validation import ReviewConflict
from database.repositories.validation_batches import ValidationBatchRepository

blueprint=Blueprint('validation',__name__,url_prefix='/annotations/validation')


def service():
    return current_app.extensions['monitor_services']['annotations']


def repository():
    svc=service()
    return current_app.extensions.get('validation_repository') or ValidationBatchRepository(svc.sessions,svc.objects,lambda:svc.methods('model'))


def private_response(template,**context):
    response=current_app.make_response(render_template(template,**context))
    response.headers.update({'Cache-Control':'private, no-store','Referrer-Policy':'no-referrer',
        'X-Frame-Options':'DENY','X-Content-Type-Options':'nosniff','X-Robots-Tag':'noindex, noarchive'})
    return response


def unavailable_response(message):
    response=private_response('annotations/validation_index.html',batches=[],error=message)
    response.status_code=503
    return response


MANAGEMENT_CSRF = 'validation_management_csrf'
FORM_FIELDS = ('name', 'purpose', 'size', 'strategy', 'seed', 'protect', 'sources', 'languages', 'model_version')


def access(csrf_key='human_review_csrf'):
    """Return an unlock response or None; use the existing token/CSRF session."""
    if not review_enabled() or not local_review_request():abort(403)
    if request.method=='POST':
        require_csrf(csrf_key)
        if request.form.get('action')=='unlock':
            unlock_review(request.form.get('review_token',''))
            session.pop(csrf_key,None)
            return redirect(request.full_path.rstrip("?"),code=303)
        if not review_authenticated():
            # Preserve only small form settings, never credentials, article text
            # or a mutation to replay. Unlock returns to GET for a fresh preview.
            if request.endpoint == 'validation.new':
                session['validation_pending_form'] = {
                    key: request.form[key][:120] for key in FORM_FIELDS if key in request.form}
            return private_response('annotations/validation_unlock.html',csrf=csrf_token(csrf_key),
                message='Your review session expired. Unlock again; nothing was saved. Your batch settings will be restored.')
    if not review_authenticated():
        return private_response('annotations/validation_unlock.html',csrf=csrf_token(csrf_key))
    return None


@blueprint.route('',methods=['GET','POST'])
def index():
    locked=access(MANAGEMENT_CSRF)
    if locked is not None:return locked
    repo=repository();error=None;batches=[]
    try:
        batches=[repo.detail(b.id) for b in repo.list()]
    except RuntimeError as exc:error=str(exc)
    except SQLAlchemyError:error='Validation storage is unavailable; verify the intended database and migration.'
    return private_response('annotations/validation_index.html',batches=batches,error=error)


@blueprint.route('/new',methods=['GET','POST'])
def new():
    locked=access(MANAGEMENT_CSRF)
    if locked is not None:return locked
    error=None;preview=None;form=request.form if request.method=='POST' else session.pop('validation_pending_form',{})
    from annotations.l2_config import L2Config
    configured_model = L2Config.from_env().model_version
    if request.method=='POST':
        try:
            sources=tuple(x.strip() for x in form.get('sources','').split(',') if x.strip())
            languages=tuple(x.strip() for x in form.get('languages','').split(',') if x.strip())
            if any(x not in ('nation','citizen','standard','star','tuko','kenyans','taifaleo') for x in sources):
                raise ValueError('Unknown publisher/source.')
            preview=repository().preview(form.get('name',''),form.get('purpose',''),int(form.get('size','0')),
                form.get('strategy',''),int(form.get('seed','42')),current_app.config['HUMAN_REVIEW_GUIDELINE_VERSION'],
                form.get('protect')=='1',sources,languages)
            if form.get('model_version') and form['model_version']!=preview['model']['model_version']:
                raise ValueError('Selected model identity does not match the verified configured artifact.')
            if form.get('action')=='create':
                if form.get('preview_digest')!=preview['configuration']['membership_sha256']:
                    raise ValueError('Candidate membership changed. Preview again before creating the draft.')
                batch=repository().create(preview)
                session.pop(MANAGEMENT_CSRF,None)
                return redirect(url_for('validation.detail',batch_id=batch.id),code=303)
            if form.get('action')!='preview':abort(400)
            # Preview was explicitly authorized at request entry. Give the user
            # a full 30-minute review window after a slow cloud-backed response.
            session['human_review_started'] = time.time()
        except (ValueError,RuntimeError) as exc:error=str(exc);preview=None
        except SQLAlchemyError:
            error='Validation storage is unavailable; verify migration installation.';preview=None
    return private_response('annotations/validation_new.html',form=form,error=error,preview=preview,
                            csrf=csrf_token(MANAGEMENT_CSRF),guideline=current_app.config['HUMAN_REVIEW_GUIDELINE_VERSION'],
                            configured_model=configured_model)


@blueprint.route('/<uuid:batch_id>',methods=['GET','POST'])
def detail(batch_id):
    locked=access(MANAGEMENT_CSRF)
    if locked is not None:return locked
    error=None
    try:
        if request.method=='POST':
            action=request.form.get('action')
            if action=='freeze':repository().freeze(batch_id)
            elif action=='complete':repository().complete(batch_id)
            else:abort(400)
            session.pop(MANAGEMENT_CSRF,None)
            return redirect(url_for('validation.detail',batch_id=batch_id),code=303)
        data=repository().detail(batch_id)
    except LookupError:abort(404)
    except ValueError as exc:
        error=str(exc);data=repository().detail(batch_id)
    except RuntimeError as exc:return unavailable_response(str(exc))
    except SQLAlchemyError:return unavailable_response('Validation storage unavailable; verify schema installation.')
    return private_response('annotations/validation_detail.html',**data,error=error,csrf=csrf_token(MANAGEMENT_CSRF))


@blueprint.get('/<uuid:batch_id>/next')
def next_member(batch_id):
    locked=access()
    if locked is not None:return locked
    try:data=repository().detail(batch_id)
    except LookupError:abort(404)
    except RuntimeError as exc:return unavailable_response(str(exc))
    except SQLAlchemyError:return unavailable_response('Validation storage unavailable; verify schema installation.')
    member=data['next_member']
    if member is None:return redirect(url_for('validation.detail',batch_id=batch_id))
    return redirect(url_for('annotations.review',annotation_id=member.automated_annotation_id,
                           batch_id=batch_id,member_id=member.id))


def review_member(annotation_id):
    """Invoked by the established /annotations/review/<annotation_id> route."""
    locked=access()
    if locked is not None:return locked
    try:
        batch_id=UUID(request.args['batch_id']);member_id=UUID(request.args['member_id'])
        data=repository().member(batch_id,member_id)
    except (ValueError,KeyError):abort(400)
    except LookupError:abort(404)
    except RuntimeError as exc:return unavailable_response(str(exc))
    except SQLAlchemyError:return unavailable_response('Validation storage unavailable; verify schema installation.')
    batch,member=data['batch'],data['member']
    if member.automated_annotation_id!=annotation_id:abort(404)
    if batch.status=='draft':abort(409)
    article=service().review_record(annotation_id)
    if article is None:abort(404)
    content=service().review_content(article)
    error=None;status=200
    if request.method=='POST':
        try:
            if request.form.get('action') not in ('save','save_next'):abort(400)
            if not content.get('article_text') and request.form.get('choice') not in ('unable_to_determine','needs_adjudication'):
                raise ValueError('Verified article text is required for a resolved reference decision.')
            if not request.form.get('reason','').strip():raise ValueError('Record an independent decision reason.')
            repository().save_decision(batch_id,member_id,request.form.get('choice',''),request.form.get('reason',''),
                current_app.config['HUMAN_REVIEWER_ID'],current_app.config['HUMAN_REVIEW_GUIDELINE_VERSION'],
                request.form.get('expected_final',''))
            current_app.logger.info('human_review_completed validation_batch_id=%s member_id=%s',batch_id,member_id)
            session.pop('human_review_csrf',None)
            flash('Independent human decision saved.' if batch.purpose=='final_test' else
                  'Independent human decision saved; the pinned prediction is now available for comparison.','success')
            if request.form.get('action')=='save_next':return redirect(url_for('validation.next_member',batch_id=batch_id),code=303)
            return redirect(url_for('annotations.review',annotation_id=annotation_id,batch_id=batch_id,member_id=member_id),code=303)
        except ReviewConflict as exc:error=str(exc);status=409
        except (ValueError,RuntimeError) as exc:error=str(exc);status=422
        except SQLAlchemyError:error='Decision could not be saved; reload before retrying.';status=503
    data=repository().member(batch_id,member_id);batch,member=data['batch'],data['member']
    comparison=None;initial=None
    if member.initial_human_validation_id:
        with service().sessions() as db:
            from database.models import HumanValidation
            initial=db.get(HumanValidation,member.initial_human_validation_id)
        if batch.purpose!='final_test':
            a=article['annotation']
            comparison={'label':a.label,'probability':a.evidence.get('gbv_probability'),
                        'method_version':a.method_version,'model_version':a.evidence.get('model_version')}
    response=private_response('annotations/validation_review.html',batch=batch,member=member,
        title=content.get('content_article',{}).get('title') or article['article'].title,
        article_text=content.get('article_text'),content_issue=content.get('content_issue'),comparison=comparison,
        initial=initial,error=error,csrf=csrf_token('human_review_csrf'))
    response.status_code=status
    return response
