"""Frozen batches integrated with exact annotations and existing append-only reviews."""
from collections import Counter
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError

from annotations.l2_config import MODEL_METHOD
from annotations.validation import ReviewConflict
from annotations.validation_batches import EMPTY_MEMBERSHIP, excluded, membership_digest, sample, training_membership
from database.models import (Article, ArticleVersion, AutomatedAnnotation, HumanValidation,
                             ValidationBatch, ValidationBatchMember)
from database.repositories.annotations import AnnotationRepository
from database.repositories.human_validations import HumanValidationRepository

MIGRATION = '20261006_add_l2_validation_batches.sql'


class ValidationBatchRepository:
    def __init__(self, sessions, objects=None, methods=None, training_provider=None):
        self.sessions, self.objects = sessions, objects
        self.methods = methods
        self.training_provider = training_provider or training_membership

    def available(self):
        return not schema_readiness(self.sessions)['missing']

    def require_schema(self):
        if not self.available():
            raise RuntimeError(f'Validation schema is not installed. Apply {MIGRATION} to the intended target first.')

    def serialize(self, session):
        if session.bind.dialect.name == 'postgresql':
            session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended('l2-validation-protection', 0))"))

    def protected_membership(self, session=None):
        """Always read current protected membership; missing schema fails closed."""
        self.require_schema()
        query = select(ValidationBatchMember).join(ValidationBatch).where(
            ValidationBatch.protect_from_training.is_(True), ValidationBatch.status != 'draft')
        if session is None:
            with self.sessions() as own:
                rows = own.scalars(query).all()
        else:
            rows = session.scalars(query).all()
        result = {k: set() for k in EMPTY_MEMBERSHIP}
        for row in rows:
            result['article_ids'].add(str(row.article_id));result['article_version_ids'].add(str(row.article_version_id))
            result['content_hashes'].add(row.content_hash)
        if rows:
            query = select(ArticleVersion.content_hash).where(ArticleVersion.article_id.in_(
                [UUID(value) for value in result['article_ids']]))
            if session is None:
                with self.sessions() as own:
                    result['content_hashes'].update(own.scalars(query))
            else:
                result['content_hashes'].update(session.scalars(query))
        return result

    def list(self):
        self.require_schema()
        with self.sessions() as session:
            return session.scalars(select(ValidationBatch).order_by(ValidationBatch.created_at.desc(), ValidationBatch.id.desc())).all()

    def detail(self, identifier):
        self.require_schema()
        with self.sessions() as session:
            try:
                query = select(ValidationBatch).where(ValidationBatch.id == UUID(str(identifier)))
            except ValueError:
                query = select(ValidationBatch).where(ValidationBatch.name == str(identifier))
            batch = session.scalar(query)
            if batch is None:
                raise LookupError('Validation batch not found.')
            members = session.scalars(select(ValidationBatchMember).where(
                ValidationBatchMember.validation_batch_id == batch.id).order_by(ValidationBatchMember.selection_order)).all()
            reviews = {r.id: r for r in session.scalars(select(HumanValidation).where(
                HumanValidation.id.in_([m.final_human_validation_id for m in members if m.final_human_validation_id])))}
        status = Counter(m.status for m in members)
        return {'batch': batch, 'members': members, 'reviews': reviews,
                'progress': {'total': len(members), 'reviewed': len(members)-status['pending'], 'pending': status['pending'],
                             'resolved': status['resolved'], 'unable_to_determine': status['unable_to_determine'],
                             'needs_adjudication': status['needs_adjudication']},
                'source_counts': dict(Counter(m.source for m in members)),
                'language_counts': dict(Counter(m.language or 'unknown' for m in members)),
                'human_counts': dict(Counter(r.human_label or r.review_decision for r in reviews.values())),
                'next_member': next((m for m in members if m.status == 'pending'), None)}

    def preview(self, name, purpose, size, strategy, seed, guideline, protect=True, sources=(), languages=()):
        self.require_schema()
        if not name.strip() or len(name) > 120 or not guideline.strip() or len(guideline) > 120 or not 1 <= size <= 10000:
            raise ValueError('Provide a name, guideline version and sample size between 1 and 10000.')
        if purpose == 'final_test' and not protect:
            raise ValueError('Final-test batches must be protected from training.')
        model = self.training_provider()
        methods = self.methods() if self.methods else None
        if methods is None:
            from annotations.schemas import DEFAULT_CONFIG
            methods = {k: DEFAULT_CONFIG.method_version(k) for k in ('L0','L1')}
            methods.update(L1_method_name='kenya_relevance_hybrid', L2_method_name=MODEL_METHOD, L2=model['method_version'])
        if methods['L2'] != model['method_version']:
            raise ValueError('Configured model identity does not match verified training provenance.')
        repository = AnnotationRepository(self.sessions)
        candidates = repository.select_candidates(['L2'], methods, only_pending=False, eligible_l2_only=True)
        current = repository.current_for_candidates([r['id'] for r in candidates], methods)
        protected = self.protected_membership()
        training = {k: set(v) for k,v in model['membership'].items()}
        training['content_hashes'].update(repository.reference_content_hashes(training['article_ids'], training['article_version_ids']))
        rows=[];seen_hashes=set();exclusions=Counter()
        for item in candidates:
            annotation = current.get((item['id'],'L2'))
            if annotation is None or annotation.method_name != MODEL_METHOD or annotation.evidence.get('model_version') != model['model_version']:
                exclusions['no_compatible_model_result'] += 1;continue
            if excluded(item, protected):
                exclusions['protected_reference'] += 1;continue
            if purpose != 'diagnostic' and excluded(item, training):
                exclusions['training_member_or_hash'] += 1;continue
            source = item['metadata']['source']
            if sources and source not in sources:
                continue
            if item['content_hash'] in seen_hashes:
                exclusions['exact_duplicate'] += 1;continue
            # Language is provenance metadata, not a reviewed language assertion.
            from annotations.service import load_verified_article
            article = load_verified_article(item, self.objects)
            language = article.get('language') or None
            if languages and language not in languages:
                continue
            seen_hashes.add(item['content_hash'])
            rows.append({**item, 'annotation_id': annotation.id, 'label': annotation.label,
                         'probability': annotation.evidence['gbv_probability'], 'source': source, 'language': language,
                         'stratum': source+'|'+(language or 'unknown')})
        selected = sample(rows,size,strategy,seed,purpose)
        config = {'sources': list(sources), 'languages': list(languages), 'language_is_unvalidated_metadata': True,
                  'eligible_pool_size': len(rows), 'exclusions': dict(exclusions),
                  'training_dataset_version': model['dataset_version'], 'training_manifest_sha256': model['manifest_sha256'],
                  'model_manifest_sha256': model['model_manifest_sha256'], 'training_record_count': model['record_count'],
                  'membership_sha256': membership_digest(selected), 'near_duplicates': 'not_grouped; research limitation',
                  'selection_policy': 'proportional_source_language_metadata' if strategy=='stratified' else strategy,
                  'inclusion_probabilities': {k: sum(r['stratum']==k for r in selected)/v for k,v in Counter(r['stratum'] for r in rows).items()}}
        return {'name': name.strip(), 'purpose': purpose, 'size': size, 'strategy': strategy, 'seed': seed,
                'guideline': guideline.strip(), 'protect': protect, 'model': model, 'configuration': config, 'selected': selected}

    def create(self, preview):
        self.require_schema()
        now=datetime.now(timezone.utc);model=preview['model']
        batch=ValidationBatch(id=uuid4(),name=preview['name'],layer='L2',purpose=preview['purpose'],
            model_method_name=MODEL_METHOD,model_method_version=model['method_version'],model_version=model['model_version'],
            guideline_version=preview['guideline'],sampling_strategy=preview['strategy'],seed=preview['seed'],
            requested_size=preview['size'],status='draft',protect_from_training=preview['protect'],
            configuration=preview['configuration'],created_at=now)
        try:
            with self.sessions.begin() as session:
                session.add(batch);session.flush()
                for i,row in enumerate(preview['selected'],1):
                    session.add(ValidationBatchMember(id=uuid4(),validation_batch_id=batch.id,
                        article_id=row['article_id'],article_version_id=row['id'],automated_annotation_id=row['annotation_id'],
                        content_hash=row['content_hash'],source=row['source'],language=row['language'],sampling_stratum=row['stratum'],
                        selection_reason='diagnostic_enrichment' if preview['strategy']=='enriched' else 'representative_random_selection',
                        selection_order=i,status='pending',created_at=now))
            return batch
        except IntegrityError as exc:
            raise ValueError('Batch name/version already exists. Use a new versioned name.') from exc

    def freeze(self, batch_id):
        model=self.training_provider()
        with self.sessions.begin() as session:
            self.serialize(session)
            batch=session.scalar(select(ValidationBatch).where(ValidationBatch.id==batch_id).with_for_update())
            if not batch or batch.status!='draft':
                raise ValueError('Only a draft can be frozen; frozen membership cannot be resampled.')
            if (batch.model_method_version!=model['method_version'] or
                    batch.configuration['model_manifest_sha256']!=model['model_manifest_sha256'] or
                    batch.configuration['training_manifest_sha256']!=model['manifest_sha256']):
                raise ValueError('Training/model provenance changed since preview.')
            members=session.scalars(select(ValidationBatchMember).where(ValidationBatchMember.validation_batch_id==batch.id)
                                    .order_by(ValidationBatchMember.selection_order)).all()
            protected=self.protected_membership(session)
            training={k:set(v) for k,v in model['membership'].items()}
            training['content_hashes'].update(AnnotationRepository(self.sessions).reference_content_hashes(training['article_ids'],training['article_version_ids']))
            if len(members)!=batch.requested_size:
                raise ValueError('Draft membership size changed.')
            snapshot=[dict(article_id=m.article_id,id=m.article_version_id,annotation_id=m.automated_annotation_id,
                           content_hash=m.content_hash,source=m.source,language=m.language,stratum=m.sampling_stratum)
                      for m in members]
            if membership_digest(snapshot)!=batch.configuration['membership_sha256']:
                raise ValueError('Draft membership changed since preview; create a new draft.')
            for member in members:
                candidate={'article_id':member.article_id,'id':member.article_version_id,'content_hash':member.content_hash}
                if excluded(candidate,protected) or (batch.purpose!='diagnostic' and excluded(candidate,training)):
                    raise ValueError('Membership conflicts with training/protected records; create a new draft.')
                annotation=session.get(AutomatedAnnotation,member.automated_annotation_id)
                version=session.get(ArticleVersion,member.article_version_id)
                if (annotation is None or version is None or annotation.article_id!=member.article_id
                        or annotation.article_version_id!=member.article_version_id or annotation.layer!='L2'
                        or annotation.method_name!=batch.model_method_name or annotation.method_version!=batch.model_method_version
                        or annotation.evidence.get('model_version')!=batch.model_version
                        or version.content_hash!=member.content_hash):
                    raise ValueError('Pinned membership lineage changed.')
            batch.status='frozen';batch.frozen_at=datetime.now(timezone.utc)
        return batch

    def member(self, batch_id, member_id):
        data=self.detail(batch_id)
        member=next((m for m in data['members'] if m.id==member_id),None)
        if member is None:raise LookupError('Batch member not found.')
        data['member']=member
        return data

    def save_decision(self, batch_id, member_id, choice, reason, identity, guideline, expected_final=None):
        """Translate a blind label into existing review vocabulary only after submission."""
        with self.sessions.begin() as session:
            self.serialize(session)
            batch=session.scalar(select(ValidationBatch).where(ValidationBatch.id==batch_id).with_for_update())
            member=session.scalar(select(ValidationBatchMember).where(ValidationBatchMember.id==member_id,
                ValidationBatchMember.validation_batch_id==batch_id).with_for_update())
            if not batch or not member or batch.status not in ('frozen','in_review'):
                raise ValueError('Only frozen/in-review batch members can be reviewed.')
            if guideline!=batch.guideline_version:
                raise ValueError('Configured guideline must match the frozen batch codebook version.')
            if str(member.final_human_validation_id or '')!=str(expected_final or ''):
                raise ReviewConflict('Batch decision changed; reload before saving.')
            annotation=session.scalar(select(AutomatedAnnotation).where(AutomatedAnnotation.id==member.automated_annotation_id).with_for_update())
            latest=session.scalar(select(HumanValidation).where(HumanValidation.automated_annotation_id==annotation.id).order_by(
                HumanValidation.created_at.desc(),HumanValidation.id.desc()).limit(1))
            decision=choice if choice in ('unable_to_determine','needs_adjudication') else 'confirmed' if choice==annotation.label else 'corrected'
            values={'decision':decision,'human_label':None if decision in ('unable_to_determine','needs_adjudication') else choice,
                    'error_category':'other' if decision=='corrected' else '', 'reason':reason, 'notes':''}
            from annotations.validation import validate_review
            fields=validate_review(annotation,**values)
            now=datetime.now(timezone.utc)
            if latest:
                from datetime import timedelta
                now=max(now,latest.created_at.replace(tzinfo=timezone.utc)+timedelta(microseconds=1))
            review=HumanValidation(id=uuid4(),automated_annotation_id=annotation.id,article_id=annotation.article_id,
                article_version_id=annotation.article_version_id,layer='L2',machine_label=annotation.label,
                machine_confidence=annotation.confidence,reviewer_identity=identity,guideline_version=guideline,
                created_at=now,supersedes_validation_id=latest.id if latest else None,**fields)
            session.add(review);session.flush()
            if member.initial_human_validation_id is None:member.initial_human_validation_id=review.id
            member.final_human_validation_id=review.id
            member.status=decision if decision in ('unable_to_determine','needs_adjudication') else 'resolved'
            batch.status='in_review'
        return review

    def complete(self,batch_id):
        with self.sessions.begin() as session:
            self.serialize(session)
            batch=session.scalar(select(ValidationBatch).where(ValidationBatch.id==batch_id).with_for_update())
            pending=session.scalar(select(ValidationBatchMember.id).where(ValidationBatchMember.validation_batch_id==batch_id,
                ValidationBatchMember.initial_human_validation_id.is_(None)).limit(1))
            if not batch or batch.status!='in_review' or pending:
                raise ValueError('Review every member before freezing accepted final decisions.')
            batch.status='completed';batch.completed_at=datetime.now(timezone.utc)
        return batch

    def evaluation_rows(self,identifier,final_experiment=False):
        data=self.detail(identifier);batch=data['batch']
        if batch.purpose=='final_test' and not final_experiment:
            raise ValueError('Final-test feedback is sealed. Use --final-experiment only for the approved final experiment.')
        with self.sessions() as session:
            rows=[(m,session.get(AutomatedAnnotation,m.automated_annotation_id),
                   session.get(HumanValidation,m.final_human_validation_id) if m.final_human_validation_id else None)
                  for m in data['members']]
        return batch,rows


def schema_readiness(sessions):
    """Read-only preflight; PostgreSQL needs installed guards as well as tables."""
    engine = sessions.kw['bind']
    inspector = inspect(engine)
    tables = ('validation_batches', 'validation_batch_members')
    missing = [name for name in tables if not inspector.has_table(name, schema='public')]
    if engine.dialect.name == 'postgresql':
        expected = {
            'validation_batches': {'uq_validation_batch_name', 'validation_batch_layer_check',
                'validation_batch_purpose_check', 'validation_batch_status_check', 'validation_batch_strategy_check',
                'validation_batch_size_check', 'validation_batch_final_protection_check', 'validation_batch_diagnostic_check'},
            'validation_batch_members': {'uq_validation_member_version', 'uq_validation_member_annotation',
                'uq_validation_member_order', 'validation_member_status_check', 'validation_member_decision_check'},
        }
        for table in tables:
            if table in missing:
                continue
            names = {row['name'] for row in inspector.get_check_constraints(table, schema='public')}
            names.update(row['name'] for row in inspector.get_unique_constraints(table, schema='public'))
            missing.extend(sorted(expected[table] - names))
        with sessions() as session:
            for table, guard in zip(tables, ('guard_l2_validation_batch', 'guard_l2_validation_member')):
                enabled = session.scalar(text("SELECT EXISTS (SELECT 1 FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
                    "JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_proc p ON p.oid=t.tgfoid "
                    "WHERE n.nspname='public' AND c.relname=:table AND t.tgname=:guard AND p.proname=:guard "
                    "AND t.tgenabled='O' AND NOT t.tgisinternal)"), {'table': table, 'guard': guard})
                if not enabled:
                    missing.append(guard)
            if 'validation_batch_members' not in missing and not any(
                    row['name']=='idx_validation_member_content' for row in inspector.get_indexes('validation_batch_members', schema='public')):
                missing.append('idx_validation_member_content')
            for table in tables:
                if table not in missing and not session.scalar(text("SELECT c.relrowsecurity FROM pg_class c "
                    "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname=:table"), {'table': table}):
                    missing.append(table+'.row_level_security')
    return {'ready': not missing, 'missing': missing, 'migration': MIGRATION,
            'dialect': engine.dialect.name}
