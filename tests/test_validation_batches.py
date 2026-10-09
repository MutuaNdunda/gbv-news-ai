"""Synthetic SQL/UI verification for batches; never use cloud or real model inference."""
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

from sqlalchemy import select

from annotations.validation import ReviewConflict
from annotations.validation_batches import evaluate_rows, membership_digest, sample, training_membership
from database.models import AutomatedAnnotation, HumanValidation, ValidationBatch, ValidationBatchMember
from database.repositories.validation_batches import ValidationBatchRepository, schema_readiness
from tests.test_l2_ui import L2ReviewFixture


class ValidationBatchTests(L2ReviewFixture):
    def setUp(self):
        super().setUp()
        self.training={'membership':{'article_ids':set(),'article_version_ids':set(),'content_hashes':set()},
            'model_version':'synthetic-model-v1','method_version':'l2-ui-model','manifest_sha256':'a'*64,
            'model_manifest_sha256':'b'*64,'dataset_version':'synthetic-data','record_count':0}
        self.repo=ValidationBatchRepository(self.sessions,self.objects,lambda:self.service.methods(),lambda:self.training)
        self.app.extensions['validation_repository']=self.repo

    def preview(self,name='synthetic-v1',purpose='development_validation',size=3,strategy='random',seed=42,protect=True):
        return self.repo.preview(name,purpose,size,strategy,seed,'synthetic-test-guide',protect)

    def management_csrf(self):
        with self.client.session_transaction() as session:
            return session['validation_management_csrf']

    def batch(self,**kwargs):
        batch=self.repo.create(self.preview(**kwargs));self.repo.freeze(batch.id);return batch

    def save_member(self,batch,member,choice='gbv',expected=None):
        return self.repo.save_decision(batch.id,member.id,choice,'Synthetic independent rationale',
            'configured-researcher','synthetic-test-guide',expected)

    def open_member(self,batch,member):
        url=f'/annotations/review/{member.automated_annotation_id}?batch_id={batch.id}&member_id={member.id}'
        self.unlock(self.l2[0])
        return url

    def test_deterministic_membership_same_seed_and_proportional_strata(self):
        a=self.preview();b=self.preview()
        self.assertEqual([r['annotation_id'] for r in a['selected']],[r['annotation_id'] for r in b['selected']])
        self.assertEqual(a['configuration'],b['configuration'])
        rows=[dict(annotation_id=i,stratum='one' if i<8 else 'two',label='gbv',probability=.9) for i in range(10)]
        selected=sample(rows,5,'stratified',12,'development_validation')
        self.assertEqual(sum(r['stratum']=='one' for r in selected),4)

    def test_training_article_version_and_hash_excluded(self):
        with self.sessions() as db:
            from database.models import ArticleVersion
            first=db.get(ArticleVersion,self.l2[0].article_version_id)
        for key,value in [('article_ids',str(self.l2[0].article_id)),('article_version_ids',str(first.id)),('content_hashes',first.content_hash)]:
            self.training['membership']={k:set() for k in self.training['membership']}
            self.training['membership'][key]={value}
            preview=self.preview(size=2)
            self.assertNotIn(self.l2[0].id,[r['annotation_id'] for r in preview['selected']])
            with self.assertRaisesRegex(ValueError,'Only 2 unseen eligible'):
                self.preview(size=3)

    def test_diagnostic_can_include_training_and_enriched_is_not_representative(self):
        self.training['membership']['article_ids']={str(a.article_id) for a in self.l2}
        self.assertEqual(len(self.preview(purpose='diagnostic',strategy='enriched')['selected']),3)
        with self.assertRaisesRegex(ValueError,'Enriched'):
            sample([{}],1,'enriched',42,'development_validation')

    def test_freeze_never_resamples_and_pins_exact_model_annotation(self):
        batch=self.batch();before=self.repo.detail(batch.id)
        with self.assertRaisesRegex(ValueError,'Only a draft'):self.repo.freeze(batch.id)
        after=self.repo.detail(batch.id)
        self.assertEqual([r.id for r in before['members']],[r.id for r in after['members']])
        self.assertEqual({r.automated_annotation_id for r in after['members']},{r.id for r in self.l2})
        self.assertEqual(batch.model_method_version,'l2-ui-model')

    def test_freeze_rechecks_training_and_protected_conflicts(self):
        draft=self.repo.create(self.preview())
        self.training['membership']['article_ids']={str(self.l2[0].article_id)}
        with self.assertRaisesRegex(ValueError,'conflicts'):self.repo.freeze(draft.id)
        self.assertEqual(self.repo.detail(draft.id)['batch'].status,'draft')

    def test_protected_members_automatic_and_final_test_forces_protection(self):
        batch=self.batch()
        protected=self.repo.protected_membership()
        self.assertEqual(protected['article_version_ids'],{str(a.article_version_id) for a in self.l2})
        with self.assertRaisesRegex(ValueError,'Only 0 unseen eligible'):self.preview(name='second',size=1)
        with self.assertRaisesRegex(ValueError,'must be protected'):self.preview(purpose='final_test',protect=False)

    def test_missing_schema_refuses_creation_and_protection(self):
        with patch.object(self.repo,'available',return_value=False):
            with self.assertRaisesRegex(RuntimeError,'not installed'):self.preview()
            with self.assertRaises(RuntimeError):self.repo.protected_membership()

    def test_initial_blind_save_reveals_pinned_machine_and_keeps_initial_across_revision(self):
        batch=self.batch();member=self.repo.detail(batch.id)['members'][0];url=self.open_member(batch,member)
        html=self.client.get(url).get_data(as_text=True)
        self.assertNotIn('Machine label:',html);self.assertNotIn('GBV probability:',html)
        self.assertNotIn('data-machine-label',html);self.assertNotIn('confirmed',html)
        self.assertIn('Choose your independent decision',html)
        response=self.client.post(url,data={'action':'save','csrf_token':self.csrf(),'choice':'not_gbv','reason':'Independent synthetic rationale','expected_final':''})
        self.assertEqual(response.status_code,303)
        html=self.client.get(response.location).get_data(as_text=True)
        self.assertIn('Machine label:',html);self.assertIn('GBV probability:',html)
        first=self.repo.member(batch.id,member.id)['member'].initial_human_validation_id
        response=self.client.post(url,data={'action':'save','csrf_token':self.csrf(),'choice':'gbv','reason':'Revised synthetic rationale','expected_final':str(first)})
        self.assertEqual(response.status_code,303)
        member=self.repo.member(batch.id,member.id)['member']
        self.assertEqual(member.initial_human_validation_id,first)
        self.assertNotEqual(member.final_human_validation_id,first)
        with self.sessions() as db:
            self.assertEqual(db.get(HumanValidation,first).human_label,'not_gbv')
            self.assertEqual(db.get(AutomatedAnnotation,member.automated_annotation_id).method_version,'l2-ui-model')

    def test_unlock_preserves_batch_context_and_does_not_show_generic_review(self):
        batch=self.batch();member=self.repo.detail(batch.id)['members'][0]
        url=f'/annotations/review/{member.automated_annotation_id}?batch_id={batch.id}&member_id={member.id}'
        html=self.client.get(url).get_data(as_text=True);self.assertNotIn('Machine result:',html)
        response=self.client.post(url,data={'action':'unlock','csrf_token':self.csrf(),'review_token':'r'*40})
        self.assertIn('batch_id=',response.location)
        self.assertNotIn('Machine label:',self.client.get(response.location).get_data(as_text=True))

    def test_security_local_csrf_trusted_identity_and_guideline(self):
        batch=self.batch();member=self.repo.detail(batch.id)['members'][0];url=self.open_member(batch,member)
        self.assertEqual(self.client.post(url,data={'action':'save'}).status_code,403)
        self.assertEqual(self.client.get(url,environ_overrides={'REMOTE_ADDR':'203.0.113.5'}).status_code,403)
        self.assertEqual(self.client.get(url,headers={'Forwarded':'for=203.0.113.5'}).status_code,403)
        response=self.client.get(url);self.assertEqual(response.headers['Cache-Control'],'private, no-store')
        response=self.client.post(url,data={'action':'save','csrf_token':self.csrf(),'choice':'gbv','reason':'Synthetic',
            'reviewer_identity':'forged','guideline_version':'forged'})
        self.assertEqual(response.status_code,303)
        with self.sessions() as db:
            review=db.get(HumanValidation,self.repo.member(batch.id,member.id)['member'].initial_human_validation_id)
            self.assertEqual(review.reviewer_identity,'configured-researcher')
            self.assertEqual(review.guideline_version,'synthetic-test-guide')

    def test_stale_batch_form_conflicts_and_does_not_change_initial(self):
        batch=self.batch();member=self.repo.detail(batch.id)['members'][0]
        first=self.save_member(batch,member)
        with self.assertRaises(ReviewConflict):self.save_member(batch,member)
        self.assertEqual(self.repo.member(batch.id,member.id)['member'].initial_human_validation_id,first.id)

    def test_progress_unresolved_and_completion_seals_final(self):
        batch=self.batch();members=self.repo.detail(batch.id)['members']
        with self.assertRaisesRegex(ValueError,'Review every'):self.repo.complete(batch.id)
        for member,label in zip(members,['gbv','unable_to_determine','needs_adjudication']):self.save_member(batch,member,label)
        progress=self.repo.detail(batch.id)['progress']
        self.assertEqual(progress,dict(total=3,reviewed=3,pending=0,resolved=1,unable_to_determine=1,needs_adjudication=1))
        self.repo.complete(batch.id)
        with self.assertRaises(ValueError):self.save_member(batch,members[0])
        rows=self.repo.evaluation_rows(batch.id)[1]
        report,_=evaluate_rows(self.repo.detail(batch.id)['batch'],rows)
        self.assertEqual(report['unresolved'],2)

    def test_batch_list_preview_draft_freeze_next_ui_and_no_accuracy(self):
        self.unlock(self.l2[0]);self.client.get('/annotations/validation/new')
        values=dict(action='preview',csrf_token=self.management_csrf(),name='ui-v1',purpose='development_validation',strategy='random',size='2',seed='42',protect='1')
        response=self.client.post('/annotations/validation/new',data=values)
        self.assertEqual(response.status_code,200);self.assertIn('Create this draft',response.get_data(as_text=True))
        preview=self.preview(name='ui-v1',size=2)
        values.update(action='create',preview_digest=preview['configuration']['membership_sha256'])
        response=self.client.post('/annotations/validation/new',data=values);self.assertEqual(response.status_code,303)
        self.client.get(response.location)
        freeze=self.client.post(response.location,data={'action':'freeze','csrf_token':self.management_csrf()});self.assertEqual(freeze.status_code,303)
        page=self.client.get(freeze.location).get_data(as_text=True)
        self.assertIn('PROTECTED FROM TRAINING: YES',page);self.assertIn('Review Next',page)
        self.assertNotIn('confusion_matrix',page)
        self.assertIn('ui-v1',self.client.get('/annotations/validation').get_data(as_text=True))

    def test_preview_create_survives_unrelated_review_token_rotation(self):
        self.unlock(self.l2[0]);self.client.get('/annotations/validation/new')
        values=dict(action='preview',csrf_token=self.management_csrf(),name='separate-form-v1',
            purpose='development_validation',strategy='random',size='2',seed='42',protect='1')
        response=self.client.post('/annotations/validation/new',data=values)
        self.assertEqual(response.status_code,200)
        # A successful ordinary review rotates its own CSRF token in another tab.
        self.client.get(self.url(self.l2[0]))
        response=self.save(self.l2[0])
        self.assertEqual(response.status_code,303)
        preview=self.preview(name=values['name'],size=2)
        values.update(action='create',preview_digest=preview['configuration']['membership_sha256'])
        response=self.client.post('/annotations/validation/new',data=values)
        self.assertEqual(response.status_code,303)
        self.assertEqual(len(self.repo.list()),1)

    def test_expired_create_requires_unlock_and_restores_only_settings_without_write(self):
        self.unlock(self.l2[0]);self.client.get('/annotations/validation/new')
        values=dict(action='create',csrf_token=self.management_csrf(),name='expiry-v1',
            purpose='development_validation',strategy='random',size='2',seed='42',protect='1',
            preview_digest='old',review_token='must-not-be-preserved')
        with self.client.session_transaction() as session:
            session['human_review_started']=0
        with patch.object(self.repo,'preview',wraps=self.repo.preview) as preview:
            response=self.client.post('/annotations/validation/new',data=values)
            preview.assert_not_called()
        self.assertEqual(response.status_code,200)
        self.assertIn('session expired',response.get_data(as_text=True))
        self.assertEqual(self.repo.list(),[])
        with self.client.session_transaction() as session:
            pending=session['validation_pending_form']
            self.assertEqual(pending['name'],'expiry-v1')
            self.assertNotIn('review_token',pending)
            self.assertNotIn('preview_digest',pending)
        response=self.client.post('/annotations/validation/new',data=dict(action='unlock',
            csrf_token=self.management_csrf(),review_token='r'*40))
        self.assertEqual(response.status_code,303)
        response=self.client.get(response.location)
        self.assertIn('value="expiry-v1"',response.get_data(as_text=True))
        self.assertIn('value="2"',response.get_data(as_text=True))
        self.assertNotIn('Create this draft',response.get_data(as_text=True))
        self.assertEqual(self.repo.list(),[])

    def test_slow_successful_preview_renews_review_window(self):
        import time
        started=time.time()
        self.unlock(self.l2[0]);self.client.get('/annotations/validation/new')
        values=dict(action='preview',csrf_token=self.management_csrf(),name='slow-v1',
            purpose='development_validation',strategy='random',size='2',seed='42',protect='1')
        with self.client.session_transaction() as session:
            session['human_review_started']=started
        with patch('app.routes.validation.time',SimpleNamespace(time=lambda:started+1900)):
            response=self.client.post('/annotations/validation/new',data=values)
        self.assertEqual(response.status_code,200)
        with self.client.session_transaction() as session:
            self.assertEqual(session['human_review_started'],started+1900)
        preview=self.preview(name='slow-v1',size=2)
        values.update(action='create',preview_digest=preview['configuration']['membership_sha256'])
        with patch('app.security.time',SimpleNamespace(time=lambda:started+1901)):
            response=self.client.post('/annotations/validation/new',data=values)
        self.assertEqual(response.status_code,303)

    def test_management_csrf_remote_proxy_and_missing_auth_still_block_writes(self):
        self.unlock(self.l2[0]);self.client.get('/annotations/validation/new')
        values=dict(action='preview',csrf_token=self.management_csrf(),name='secure-v1',
            purpose='development_validation',strategy='random',size='2',seed='42',protect='1')
        for extra in ({'environ_overrides':{'REMOTE_ADDR':'203.0.113.5'}},
                      {'headers':{'Forwarded':'for=203.0.113.5'}}):
            self.assertEqual(self.client.post('/annotations/validation/new',data=values,**extra).status_code,403)
        values['csrf_token']='bad'
        response=self.client.post('/annotations/validation/new',data=values)
        self.assertEqual(response.status_code,403)
        self.assertIn('Reload the page',response.get_data(as_text=True))
        self.assertEqual(self.repo.list(),[])

    def test_final_test_evaluation_requires_explicit_final_experiment(self):
        batch=self.batch(purpose='final_test')
        with self.assertRaisesRegex(ValueError,'sealed'):self.repo.evaluation_rows(batch.id)

    def test_evaluator_correct_math_and_diagnostic_warning(self):
        batch=SimpleNamespace(id=uuid4(),name='synthetic-eval',purpose='development_validation',status='completed',
            model_version='model',model_method_name='afroxlmr_gbv_relevance',model_method_version='method',
            guideline_version='guide',requested_size=6,sampling_strategy='random',seed=42,configuration={})
        rows=[]
        for index,(human,machine) in enumerate([('gbv','gbv'),('gbv','not_gbv'),('not_gbv','gbv'),('not_gbv','not_gbv'),('borderline','gbv'),('gbv','borderline')]):
            a=SimpleNamespace(id=uuid4(),article_id=uuid4(),article_version_id=uuid4(),method_name=batch.model_method_name,
                method_version='method',label=machine,evidence={'gbv_probability':.5,'model_version':'model'})
            review=SimpleNamespace(id=uuid4(),automated_annotation_id=a.id,human_label=human,review_decision='confirmed',
                article_id=a.article_id,article_version_id=a.article_version_id,guideline_version='guide')
            member=SimpleNamespace(id=uuid4(),article_id=a.article_id,article_version_id=a.article_version_id,
                automated_annotation_id=a.id,initial_human_validation_id=review.id,final_human_validation_id=review.id,
                content_hash=str(index),source='synthetic',language=None,sampling_stratum='synthetic',selection_order=index)
            rows.append((member,a,review))
        batch.configuration['membership_sha256']=membership_digest([
            dict(article_id=m.article_id,id=m.article_version_id,annotation_id=m.automated_annotation_id,
                 content_hash=m.content_hash,source=m.source,language=m.language,stratum=m.sampling_stratum) for m,_,_ in rows])
        report,pairs=evaluate_rows(batch,rows)
        self.assertEqual(report['confusion_matrix'],dict(TP=1,FP=1,TN=1,FN=1))
        self.assertEqual(report['metrics'],dict(accuracy=.5,precision=.5,recall=.5,f1=.5))
        self.assertEqual(report['binary_evaluable'],4);self.assertEqual(report['excluded_from_binary_metrics'],2)
        self.assertEqual(report['model_abstention_rate'],1/6)
        self.assertEqual(evaluate_rows(batch,rows),(report,pairs))
        batch.purpose='diagnostic';batch.sampling_strategy='enriched'
        report,_=evaluate_rows(batch,rows);self.assertIsNone(report['metrics']);self.assertIn('DIAGNOSTIC',report['warning'])

    def test_verified_training_manifest_required(self):
        with patch('annotations.validation_batches.model_identity',return_value=({'training_dataset_version':'missing-data'},'method')):
            with self.assertRaisesRegex(ValueError,'unavailable'):training_membership(SimpleNamespace())

    def test_protected_members_excluded_from_reviewed_mixed_and_weak_exports(self):
        import tempfile
        from pathlib import Path
        from annotations.l2_datasets import build_development
        from annotations.l2_training import build_bootstrap,ROOT
        from database.repositories.annotations import AnnotationRepository
        self.service.save_review(self.weak.id,dict(decision='corrected',human_label='gbv',
            error_category='other',reason='Synthetic',notes=''),'configured-researcher','synthetic-test-guide',None)
        with tempfile.TemporaryDirectory(dir=ROOT/'data') as directory:
            repo=AnnotationRepository(self.sessions)
            first=build_development(repo,self.service.reviews,self.objects,Path(directory)/'before','mixed-effective')
            self.assertEqual(first['record_count'],1)
            self.batch()
            self.objects.read_json.reset_mock()
            for policy in ('reviewed-only','mixed-effective'):
                manifest=build_development(repo,self.service.reviews,self.objects,Path(directory)/policy,policy)
                self.assertEqual(manifest['record_count'],0)
                self.assertGreater(manifest['skipped']['held_out_reference'],0)
            manifest=build_bootstrap(repo,self.objects,Path(directory)/'weak')
            self.assertEqual(manifest['record_count'],0)
            self.assertGreater(manifest['skipped']['held_out_reference'],0)
            self.objects.read_json.assert_not_called()

    def test_unfrozen_draft_does_not_protect_and_interleaved_drafts_conflict(self):
        one=self.repo.create(self.preview(name='one'))
        two=self.repo.create(self.preview(name='two'))
        self.assertFalse(any(self.repo.protected_membership().values()))
        self.repo.freeze(one.id)
        with self.assertRaisesRegex(ValueError,'conflicts'):self.repo.freeze(two.id)

    def test_wrong_model_identity_and_guideline_rejected(self):
        self.training['method_version']='wrong'
        with self.assertRaisesRegex(ValueError,'identity'):self.preview()
        self.training['method_version']='l2-ui-model'
        batch=self.batch();member=self.repo.detail(batch.id)['members'][0]
        with self.assertRaisesRegex(ValueError,'guideline'):self.repo.save_decision(batch.id,member.id,'gbv','Synthetic','trusted','wrong')

    def test_missing_schema_ui_fails_closed_and_existing_annotation_pages_work(self):
        self.unlock(self.l2[0])
        with patch.object(self.repo,'available',return_value=False):
            html=self.client.get('/annotations/validation').get_data(as_text=True)
            self.assertIn('not installed',html)
            self.assertEqual(self.client.get('/annotations/l2?mode=weak').status_code,200)

    def test_draft_snapshot_tampering_refused_at_freeze(self):
        draft=self.repo.create(self.preview())
        with self.sessions.begin() as db:
            member=db.scalar(select(ValidationBatchMember).where(ValidationBatchMember.validation_batch_id==draft.id))
            member.language='changed'
        with self.assertRaisesRegex(ValueError,'membership changed'):self.repo.freeze(draft.id)

    def test_final_test_feedback_stays_hidden_after_initial_save(self):
        batch=self.batch(purpose='final_test');member=self.repo.detail(batch.id)['members'][0]
        url=self.open_member(batch,member)
        self.save_member(batch,member)
        html=self.client.get(url).get_data(as_text=True)
        self.assertNotIn('Machine label:',html);self.assertNotIn('GBV probability:',html)
        self.assertIn('feedback remains sealed',html)

    def test_evaluation_stays_pinned_after_normal_review_changes(self):
        batch=self.batch();members=self.repo.detail(batch.id)['members']
        for member in members:self.save_member(batch,member)
        self.repo.complete(batch.id)
        before=evaluate_rows(*self.repo.evaluation_rows(batch.id))
        member=members[0]
        final=self.repo.member(batch.id,member.id)['member'].final_human_validation_id
        self.service.save_review(member.automated_annotation_id,dict(decision='unable_to_determine',human_label='',
            error_category='',reason='',notes=''),'configured-researcher','synthetic-test-guide',str(final))
        self.assertEqual(evaluate_rows(*self.repo.evaluation_rows(batch.id)),before)

    def test_evaluator_refuses_wrong_reference_and_membership_digest(self):
        batch=self.batch();members=self.repo.detail(batch.id)['members']
        for member in members:self.save_member(batch,member)
        self.repo.complete(batch.id)
        stored,rows=self.repo.evaluation_rows(batch.id)
        rows[0][2].guideline_version='wrong'
        with self.assertRaisesRegex(ValueError,'review lineage'):evaluate_rows(stored,rows)
        rows[0][2].guideline_version=stored.guideline_version
        rows[0][0].content_hash='wrong'
        with self.assertRaisesRegex(ValueError,'digest'):evaluate_rows(stored,rows)

    def test_private_evaluation_cli_deterministic_hashes_and_no_overwrite(self):
        import hashlib
        import tempfile
        from pathlib import Path
        from annotations.l2_training import ROOT
        from scripts.evaluate_l2_validation import main
        batch=self.batch()
        for member in self.repo.detail(batch.id)['members']:self.save_member(batch,member)
        self.repo.complete(batch.id)
        with tempfile.TemporaryDirectory(dir=ROOT/'data') as directory, \
                patch('scripts.evaluate_l2_validation.create_session_factory',return_value=self.sessions):
            one=Path(directory)/'one';two=Path(directory)/'two'
            self.assertEqual(main(['--batch',batch.name,'--output-dir',str(one)]),0)
            self.assertEqual(main(['--batch',batch.name,'--output-dir',str(two)]),0)
            for file in ('manifest.json','evaluation_pairs.jsonl','evaluation_report.json'):
                self.assertEqual((one/file).read_bytes(),(two/file).read_bytes())
            manifest=json.loads((one/'manifest.json').read_text())
            self.assertEqual(manifest['evaluation_pairs_sha256'],hashlib.sha256((one/'evaluation_pairs.jsonl').read_bytes()).hexdigest())
            self.assertEqual(main(['--batch',batch.name,'--output-dir',str(one)]),2)

    def test_training_cli_rechecks_old_exports_before_model_loading(self):
        from scripts.train_l2_classifier import main
        batch=self.batch();member=self.repo.detail(batch.id)['members'][0]
        row=dict(article_id=str(member.article_id),article_version_id=str(member.article_version_id),content_hash=member.content_hash)
        with patch('database.session.create_session_factory',return_value=self.sessions), \
                patch('annotations.l2_training.load_training_data',return_value=([row],{})), \
                patch('scripts.train_l2_classifier.train_classifier') as train:
            self.assertEqual(main(['--dataset-dir','synthetic','--output-dir','synthetic','--model-version','synthetic']),2)
            train.assert_not_called()

    def test_postgres_readiness_refuses_tables_without_enabled_guards(self):
        sessions=MagicMock()
        sessions.kw={'bind':SimpleNamespace(dialect=SimpleNamespace(name='postgresql'))}
        inspector=Mock()
        inspector.has_table.return_value=True
        tables={'validation_batches':ValidationBatch.__table__,'validation_batch_members':ValidationBatchMember.__table__}
        inspector.get_check_constraints.side_effect=lambda table,**kwargs:[{'name':c.name} for c in tables[table].constraints]
        inspector.get_unique_constraints.return_value=[]
        inspector.get_indexes.return_value=[{'name':'idx_validation_member_content'}]
        sessions.return_value.__enter__.return_value.scalar.side_effect=[True,False,True,True]
        with patch('database.repositories.validation_batches.inspect',return_value=inspector):
            state=schema_readiness(sessions)
        self.assertFalse(state['ready']);self.assertIn('guard_l2_validation_member',state['missing'])

    def test_missing_schema_batch_links_return_private_failure(self):
        batch=self.batch();member=self.repo.detail(batch.id)['members'][0];url=self.open_member(batch,member)
        with patch.object(self.repo,'available',return_value=False):
            for path in (f'/annotations/validation/{batch.id}',f'/annotations/validation/{batch.id}/next',url):
                response=self.client.get(path)
                self.assertEqual(response.status_code,503)
                self.assertEqual(response.headers['Cache-Control'],'private, no-store')
                self.assertNotIn('Machine label:',response.get_data(as_text=True))

    def test_unverified_text_blocks_resolved_blind_reference(self):
        batch=self.batch();member=self.repo.detail(batch.id)['members'][0];url=self.open_member(batch,member)
        with patch.object(self.service,'review_content',return_value={'article_text':None,'content_issue':'Cannot verify extraction'}):
            response=self.client.post(url,data={'action':'save','csrf_token':self.csrf(),'choice':'gbv','reason':'Synthetic'})
            self.assertEqual(response.status_code,422)
            self.assertNotIn('Machine label:',response.get_data(as_text=True))
            self.assertIsNone(self.repo.member(batch.id,member.id)['member'].initial_human_validation_id)
            response=self.client.post(url,data={'action':'save','csrf_token':self.csrf(),'choice':'unable_to_determine','reason':'Cannot verify text'})
            self.assertEqual(response.status_code,303)
