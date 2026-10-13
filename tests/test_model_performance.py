"""Synthetic accepted references, private reports and protected Flask paths."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import select

from annotations.evaluation_reports import persist_report, load_bundle, checksum
from annotations.l2_evaluation import classification, probability_analysis, thresholds, bootstrap_intervals
from annotations.l2_training import ROOT
from annotations.reference_quality import blinded_audit_sample
from annotations.validation_batches import evaluate_rows, membership_digest
from database.models import HumanValidation, ValidationBatch, ValidationBatchMember, AutomatedAnnotation
from database.repositories.validation_batches import ValidationBatchRepository
from tests.test_l2_ui import L2ReviewFixture


def synthetic(cohort):
    batch=SimpleNamespace(id=uuid4(),name='synthetic-evaluation',status='completed',purpose='development_validation',
        model_version='synthetic-model',model_method_name='afroxlmr_gbv_relevance',model_method_version='synthetic-method',
        guideline_version='synthetic-guide',requested_size=len(cohort),sampling_strategy='random',seed=42,
        configuration={},completed_at='2026-10-13T00:00:00Z')
    rows=[]
    for index,(human, probability) in enumerate(cohort):
        machine='gbv' if probability>=.8 else 'not_gbv' if probability<=.2 else 'borderline'
        a=SimpleNamespace(id=uuid4(),article_id=uuid4(),article_version_id=uuid4(),layer='L2',
            method_name=batch.model_method_name,method_version=batch.model_method_version,label=machine,
            evidence=dict(model_version=batch.model_version,gbv_probability=probability,positive_threshold=.8,negative_threshold=.2))
        r=SimpleNamespace(id=uuid4(),automated_annotation_id=a.id,article_id=a.article_id,article_version_id=a.article_version_id,
            human_label=human,review_decision='needs_adjudication' if human is None else 'confirmed' if human==machine else 'corrected',
            guideline_version=batch.guideline_version,notes='Bulk review: title-only decision; verified body not opened.')
        m=SimpleNamespace(id=uuid4(),article_id=a.article_id,article_version_id=a.article_version_id,automated_annotation_id=a.id,
            content_hash=str(index),source='nation' if index%2 else 'taifaleo',language='en' if index%2 else None,
            sampling_stratum='synthetic',selection_order=index,initial_human_validation_id=r.id,final_human_validation_id=r.id)
        rows.append((m,a,r))
    batch.configuration['membership_sha256']=membership_digest([dict(article_id=m.article_id,id=m.article_version_id,
        annotation_id=m.automated_annotation_id,content_hash=m.content_hash,source=m.source,language=m.language,
        stratum=m.sampling_stratum) for m,_,_ in rows])
    return batch,rows


class MetricTests(unittest.TestCase):
    def test_matrix_classification_and_abstention_denominators(self):
        b,rows=synthetic([('gbv',.9),('gbv',.1),('not_gbv',.9),('not_gbv',.1),('gbv',.5),('not_gbv',.5),('borderline',.9),(None,.5)])
        report,pairs=evaluate_rows(b,rows); d=report['classification']['metric_details']
        self.assertEqual(report['confusion_matrix'],dict(TP=1,TN=1,FP=1,FN=1))
        self.assertEqual(report['binary_coverage']['value'],4/6)
        self.assertEqual(report['abstention_all']['value'],3/8)
        self.assertEqual(report['abstention_resolved']['value'],2/6)
        self.assertEqual(report['human_uncertainty_exclusions'],2)
        for key in ('accuracy','precision','recall','f1','macro_f1','specificity','balanced_accuracy','negative_predictive_value'):
            self.assertEqual(d[key]['value'],.5)
        self.assertEqual(report['probability']['support'],6)
        self.assertEqual((report['abstained_human_gbv'],report['abstained_human_not_gbv']),(1,1))

    def test_per_class_macro_weighted_and_micro(self):
        b,rows=synthetic([('gbv',.9)]*3+[('gbv',.1)]+[('not_gbv',.9)]*2+[('not_gbv',.1)]*4)
        r,_=evaluate_rows(b,rows); c=r['classification']; a=c['aggregates']
        self.assertAlmostEqual(c['classes']['gbv']['f1']['value'],6/9)
        self.assertAlmostEqual(c['classes']['not_gbv']['f1']['value'],8/11)
        self.assertAlmostEqual(a['macro']['f1']['value'],(6/9+8/11)/2)
        self.assertAlmostEqual(a['weighted']['f1']['value'],((6/9)*4+(8/11)*6)/10)
        self.assertEqual(a['micro']['f1']['value'],.7)

    def test_unsupported_classes_empty_predictions_and_uncertainty(self):
        for cohort in ([('not_gbv',.1)]*4,[('gbv',.5)]*3,[(None,.5)]):
            b,rows=synthetic(cohort); r,_=evaluate_rows(b,rows)
            self.assertIsNone(r['roc_auc'])
            self.assertIsNone(r['classification']['metric_details']['macro_f1']['value'])
        b,rows=synthetic([('not_gbv',.1)]*4); r,_=evaluate_rows(b,rows)
        for key in ('precision','recall','f1'):
            self.assertIsNone(r['classification']['classes']['gbv'][key]['value'])

    def test_probability_auc_ties_ap_and_included_abstentions(self):
        b,rows=synthetic([('gbv',.9),('not_gbv',.8),('gbv',.6),('not_gbv',.1)])
        r,_=evaluate_rows(b,rows); p=r['probability']
        self.assertEqual(p['support'],4)
        self.assertEqual(p['roc_auc'],.75)
        self.assertAlmostEqual(p['average_precision'],(1+2/3)/2)
        self.assertAlmostEqual(p['brier_score']['value'],(.01+.64+.16+.01)/4)
        b,rows=synthetic([('gbv',.5),('not_gbv',.5)]); r,_=evaluate_rows(b,rows)
        self.assertEqual(r['roc_auc'],.5);self.assertEqual(r['pr_auc'],.5)
        self.assertEqual(sum(x['n'] for x in r['probability']['calibration_bins']),2)
        self.assertEqual(r['probability']['expected_calibration_error']['value'],0)

    def test_probability_boundaries_and_no_fit(self):
        b,rows=synthetic([('gbv',0),('not_gbv',1)])
        with patch('annotations.l2.TransformerPredictor') as model:
            r,_=evaluate_rows(b,rows); model.assert_not_called()
        self.assertEqual(r['probability']['brier_score']['value'],1)
        self.assertTrue(r['probability']['log_loss']['value']>30)
        self.assertEqual(r['probability']['calibration_bins'][0]['n'],1)
        self.assertEqual(r['probability']['calibration_bins'][-1]['n'],1)

    def test_threshold_exploration_is_pure_and_final_test_blocked(self):
        b,rows=synthetic([('gbv',.8),('not_gbv',.2),('gbv',.5)])
        r,pairs=evaluate_rows(b,rows); original=deepcopy(pairs)
        t=thresholds(pairs,'development_validation')
        self.assertEqual(pairs,original)
        official=next(x for x in t['points'] if x['positive_threshold']==.8)
        self.assertEqual(official['coverage'],r['binary_coverage']['value'])
        self.assertEqual(official['false_negatives'],r['confusion_matrix']['FN'])
        self.assertFalse(thresholds(pairs,'final_test')['enabled'])
        self.assertFalse(thresholds(pairs,'diagnostic')['enabled'])

    def test_pending_identity_probability_threshold_and_weak_fail_closed(self):
        for corrupt in ('pending','model','guideline','weak','probability','threshold','digest'):
            b,rows=synthetic([('gbv',.9)])
            if corrupt=='pending': b.status='in_review'
            if corrupt=='model': rows[0][1].evidence['model_version']='wrong'
            if corrupt=='guideline': rows[0][2].guideline_version='wrong'
            if corrupt=='weak': b.model_method_name=rows[0][1].method_name='gbv_weak_supervision'
            if corrupt=='probability': rows[0][1].evidence['gbv_probability']=float('nan')
            if corrupt=='threshold': rows[0][1].label='not_gbv'
            if corrupt=='digest': b.configuration['membership_sha256']='wrong'
            with self.subTest(corrupt=corrupt), self.assertRaises(ValueError): evaluate_rows(b,rows)

    def test_subgroups_metadata_is_not_publisher_language(self):
        b,rows=synthetic([('gbv',.9),('not_gbv',.1)])
        r,_=evaluate_rows(b,rows)
        self.assertIn('Unknown',r['subgroups']['language'])
        self.assertNotIn('Swahili',r['subgroups']['language'])
        self.assertNotIn('standard',r['subgroups']['source'])
        self.assertEqual(r['subgroups']['source']['taifaleo']['sample_size'],1)
        self.assertIsNone(r['subgroups']['source']['taifaleo']['metric_details']['macro_f1']['value'])

    def test_intervals_deterministic_withheld_for_small_class_support(self):
        b,rows=synthetic([('gbv',.9)]*12+[('gbv',.1)]*4+[('not_gbv',.9)]*3+[('not_gbv',.1)]*14)
        r,pairs=evaluate_rows(b,rows)
        self.assertEqual(bootstrap_intervals(r['classification']),r['uncertainty'])
        self.assertIsNotNone(r['uncertainty']['macro_f1'])
        b,rows=synthetic([('gbv',.9),('not_gbv',.1)])
        self.assertIsNone(evaluate_rows(b,rows)[0]['uncertainty']['f1'])

    def test_diagnostic_suppresses_added_metrics(self):
        b,rows=synthetic([('gbv',.9),('not_gbv',.1)]);b.purpose='diagnostic'
        r,_=evaluate_rows(b,rows)
        for key in ('metrics','classification','probability','subgroups','uncertainty'):
            self.assertIsNone(r[key])


class PerformanceRoutesTests(L2ReviewFixture):
    def setUp(self):
        super().setUp()
        self.training=dict(membership={k:set() for k in ('article_ids','article_version_ids','content_hashes')},
            model_version='synthetic-model-v1',method_version='l2-ui-model',manifest_sha256='a'*64,
            model_manifest_sha256='b'*64,dataset_version='synthetic-data',record_count=0)
        self.repo=ValidationBatchRepository(self.sessions,self.objects,lambda:self.service.methods(),lambda:self.training)
        self.app.extensions['validation_repository']=self.repo
        self.directory=tempfile.TemporaryDirectory(dir=ROOT/'data');self.addCleanup(self.directory.cleanup)
        self.root=Path(self.directory.name)
        self.app.config.update(MODEL_PERFORMANCE_ENABLED=True,MODEL_PERFORMANCE_TOKEN='p'*40,
            MODEL_PERFORMANCE_REPORT_ROOT=str(self.root))

    def batch(self, name='synthetic-performance', completed=False, purpose='development_validation'):
        b=self.repo.create(self.repo.preview(name,purpose,3,'random',42,'synthetic-test-guide',True))
        self.repo.freeze(b.id)
        for index,m in enumerate(self.repo.detail(b.id)['members']):
            self.repo.save_decision(b.id,m.id,'gbv' if index==0 else 'not_gbv','Independent synthetic reason',
                'configured-researcher','synthetic-test-guide',verified_body=index==0)
        if completed:self.repo.complete(b.id)
        return self.repo.detail(b.id)['batch']

    def persist(self,b):
        b,rows=self.repo.evaluation_rows(b.id,final_experiment=b.purpose=='final_test')
        r,pairs=evaluate_rows(b,rows);r['reference_quality']=self.repo.reference_audit(b.id,verify_training=True)
        r['final_experiment_released']=b.purpose=='final_test'
        r['reference_quality'].pop('audit_candidates')
        path=self.root/b.name;persist_report(path,b,r,pairs)
        return path

    def unlock_performance(self):
        self.client.get('/annotations/model-performance')
        with self.client.session_transaction() as session:token=session['model_performance_csrf']
        return self.client.post('/annotations/model-performance',data=dict(action='unlock',csrf_token=token,performance_token='p'*40))

    def test_reviewer_token_cannot_access_comparisons_and_proxy_remote_blocked(self):
        b=self.batch(completed=True);self.persist(b)
        self.unlock(self.l2[0])
        html=self.client.get('/annotations/model-performance').get_data(as_text=True)
        self.assertIn('Unlock Model Performance',html);self.assertNotIn('confusion matrix',html)
        self.client.get('/annotations/model-performance')
        with self.client.session_transaction() as session:token=session['model_performance_csrf']
        self.assertEqual(self.client.post('/annotations/model-performance',data=dict(action='unlock',csrf_token=token,performance_token='r'*40)).status_code,403)
        self.unlock_performance()
        for extra in ({'environ_overrides':{'REMOTE_ADDR':'203.0.113.8'}},{'headers':{'X-Forwarded-For':'127.0.0.1'}}):
            for path in ('/annotations/model-performance',f'/annotations/model-performance/{b.id}/errors'):
                self.assertEqual(self.client.get(path,**extra).status_code,403)
        self.app.config['MODEL_PERFORMANCE_TOKEN']='r'*40
        self.assertEqual(self.client.get('/annotations/model-performance').status_code,403)

    def test_pending_has_progress_no_scores_and_no_get_writes_or_inference(self):
        b=self.batch();self.unlock_performance();self.objects.read_json.reset_mock()
        def no_write(connection,cursor,statement,parameters,context,executemany):
            self.assertFalse(statement.lstrip().upper().startswith(('INSERT','UPDATE','DELETE')))
        from sqlalchemy import event
        engine=self.sessions.kw['bind'];event.listen(engine,'before_cursor_execute',no_write)
        try:
            with patch('annotations.validation_batches.evaluate_rows') as evaluate,patch('annotations.l2.TransformerPredictor') as model:
                response=self.client.get('/annotations/model-performance')
                evaluate.assert_not_called();model.assert_not_called()
            self.assertEqual(response.status_code,200)
            html=response.get_data(as_text=True)
            self.assertIn('Evaluation pending',html);self.assertNotIn('Conditional binary accuracy uses',html)
            self.assertEqual(self.repo.detail(b.id)['batch'].status,'in_review')
            self.assertEqual(response.headers['Cache-Control'],'private, no-store')
            self.objects.read_json.assert_not_called()
            self.assertEqual(self.client.get(f'/annotations/model-performance/{b.id}/errors').status_code,409)
        finally:event.remove(engine,'before_cursor_execute',no_write)

    def test_completed_report_render_filters_exports_no_body_by_default(self):
        b=self.batch(completed=True);self.persist(b);self.unlock_performance();self.objects.read_json.reset_mock()
        with patch('annotations.validation_batches.evaluate_rows') as evaluate:
            response=self.client.get('/annotations/model-performance');evaluate.assert_not_called()
        self.assertEqual(response.status_code,200)
        html=response.get_data(as_text=True)
        for text in ('Conditional binary accuracy','confusion matrix','Publisher and language','Exploratory thresholds','Research integrity'):
            self.assertIn(text,html)
        path=f'/annotations/model-performance/{b.id}/errors'
        response=self.client.get(path);self.assertEqual(response.status_code,200)
        self.assertIn('accepted frozen human references',response.get_data(as_text=True))
        response=self.client.get(path+'?error_category=FN&min_probability=0&max_probability=0.2')
        self.assertEqual(response.status_code,200)
        self.objects.read_json.assert_not_called()
        for name in ('evaluation_report.json','manifest.json','classification.csv','confusion_matrix.csv','subgroups.csv','errors.csv'):
            response=self.client.get(f'/annotations/model-performance/{b.id}/export/{name}')
            self.assertEqual(response.status_code,200)
            self.assertNotIn('article_text',response.get_data(as_text=True))
            self.assertNotIn('configured-researcher',response.get_data(as_text=True))
            self.assertEqual(response.headers['Cache-Control'],'private, no-store')
            response.close()
        self.assertEqual(self.client.get(f'/annotations/model-performance/{b.id}/export/evaluation_pairs.jsonl').status_code,404)

    def test_active_blinded_batch_blocks_all_comparison_endpoints(self):
        b=self.batch(completed=True);self.persist(b)
        with self.sessions.begin() as db:
            other=ValidationBatch(id=uuid4(),name='active-blind',layer='L2',purpose='development_validation',
                model_method_name=b.model_method_name,model_method_version=b.model_method_version,model_version=b.model_version,
                guideline_version=b.guideline_version,sampling_strategy='random',seed=42,requested_size=1,status='in_review',
                protect_from_training=True,configuration={},created_at=self.now)
            db.add(other)
        self.unlock_performance()
        html=self.client.get('/annotations/model-performance?batch='+str(b.id)).get_data(as_text=True)
        self.assertIn('blinded batch assignment is active',html);self.assertNotIn('Conditional binary accuracy uses',html)
        for path in (f'/annotations/model-performance/{b.id}/errors',f'/annotations/model-performance/{b.id}/export/errors.csv'):
            self.assertEqual(self.client.get(path).status_code,409)

    def test_blinded_audit_sample_and_append_only_full_body_revision(self):
        b=self.batch();self.unlock(self.l2[0]);data=self.repo.reference_audit(b.id,verify_training=True)
        sample=blinded_audit_sample(data['audit_candidates'])
        self.assertEqual(sample,blinded_audit_sample(data['audit_candidates']))
        altered=[dict(r,model_label='secret',gbv_probability=.1,error_category='secret') for r in data['audit_candidates']]
        self.assertEqual([r['member_id'] for r in sample],[r['member_id'] for r in blinded_audit_sample(altered)])
        response=self.client.get(f'/annotations/model-performance/{b.id}/reference-audit?evidence=proposed_sample')
        html=response.get_data(as_text=True);self.assertEqual(response.status_code,200)
        self.assertNotIn('Machine label:',html);self.assertNotIn('GBV probability:',html)
        m=self.repo.detail(b.id)['members'][0];initial=m.initial_human_validation_id;old=m.final_human_validation_id
        url=f'/annotations/review/{m.automated_annotation_id}?batch_id={b.id}&member_id={m.id}&blind=1'
        html=self.client.get(url).get_data(as_text=True);self.assertNotIn('Machine label:',html)
        response=self.client.post(url,data=dict(action='save',csrf_token=self.csrf(),choice='not_gbv',reason='Full synthetic context',expected_final=str(old)))
        self.assertEqual(response.status_code,303);self.assertIn('blind=1',response.location)
        html=self.client.get(response.location).get_data(as_text=True);self.assertNotIn('Machine label:',html)
        current=self.repo.member(b.id,m.id)['member'];self.assertEqual(current.initial_human_validation_id,initial)
        self.assertNotEqual(current.final_human_validation_id,old)
        with self.sessions() as db:
            self.assertIn('verified body opened',db.get(HumanValidation,current.final_human_validation_id).notes)
            self.assertIsNotNone(db.get(HumanValidation,old))

    def test_report_checksum_lineage_and_symlink_rejection(self):
        b=self.batch(completed=True);path=self.persist(b);members=self.repo.detail(b.id)['members']
        self.assertTrue(load_bundle(path,b,members,self.root))
        members[0].final_human_validation_id=uuid4()
        with self.assertRaisesRegex(ValueError,'pointers'):load_bundle(path,b,members,self.root)
        members=self.repo.detail(b.id)['members']
        (path/'classification.csv').write_text('tampered')
        with self.assertRaisesRegex(ValueError,'checksum'):load_bundle(path,b,members,self.root)
        link=self.root/'linked';link.symlink_to(path, target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'Unsafe'):load_bundle(link,b,members,self.root)

    def test_final_test_report_no_threshold_interface_and_training_overlap_gate(self):
        b=self.batch(completed=True,purpose='final_test');self.persist(b);self.unlock_performance()
        html=self.client.get('/annotations/model-performance').get_data(as_text=True)
        self.assertIn('Final Test',html)
        self.assertIn('Threshold exploration is restricted',html)
        self.assertNotIn('Selective risk versus coverage',html)
        self.training['membership']['article_ids']={str(self.l2[0].article_id)}
        audit=self.repo.reference_audit(b.id,verify_training=True)
        self.assertTrue(audit['issues']);self.assertGreater(audit['counts']['training_overlap'],0)

    def test_completion_requires_explicit_reference_acceptance(self):
        b=self.batch();self.unlock(self.l2[0]);path=f'/annotations/validation/{b.id}'
        self.client.get(path)
        with self.client.session_transaction() as session:csrf=session['validation_management_csrf']
        response=self.client.post(path,data=dict(action='complete',csrf_token=csrf))
        self.assertIn('Explicitly accept',response.get_data(as_text=True))
        self.assertEqual(self.repo.detail(b.id)['batch'].status,'in_review')

    def test_protected_body_uses_generation_reader_and_expiry_blocks_access(self):
        b=self.batch(completed=True);self.persist(b);self.unlock_performance()
        m=self.repo.detail(b.id)['members'][0]
        self.objects.read_json.reset_mock()
        path=f'/annotations/model-performance/{b.id}/errors/{m.id}/body'
        response=self.client.get(path)
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json['article_text'])
        self.assertEqual(self.objects.read_json.call_args.kwargs['generation'],'123')
        self.assertEqual(response.headers['Cache-Control'],'private, no-store')
        with self.client.session_transaction() as session:session['performance_started']=0
        self.objects.read_json.reset_mock()
        response=self.client.get(path)
        self.assertNotIn('article_text',response.get_data(as_text=True))
        self.objects.read_json.assert_not_called()

    def test_title_only_warning_and_initial_final_chain_audit(self):
        b=self.batch();m=self.repo.detail(b.id)['members'][0]
        with self.sessions.begin() as db:
            r=db.get(HumanValidation,m.final_human_validation_id)
            r.notes='Bulk review: title-only decision; verified body not opened.'
        audit=self.repo.reference_audit(b.id,verify_training=True)
        self.assertEqual(audit['evidence_basis']['title_only'],1)
        self.assertIn('Title-only reference labels',audit['warnings'][0])
        self.assertEqual(audit['counts']['reference_chain_issues'],0)
        self.assertTrue(audit['technical_integrity_ready'])
        self.assertFalse(audit['technical_ready'])
        self.assertEqual(audit['reference_quality_ready'],'requires_researcher_acceptance')

    def test_identity_membership_and_calculation_time_tampering_rejected(self):
        b=self.batch(completed=True);path=self.persist(b);members=self.repo.detail(b.id)['members']
        original=b.guideline_version;b.guideline_version='wrong-guideline'
        with self.assertRaisesRegex(ValueError,'identity'):load_bundle(path,b,members,self.root)
        b.guideline_version=original
        members[0].content_hash='wrong-hash'
        with self.assertRaisesRegex(ValueError,'membership'):load_bundle(path,b,members,self.root)
        members=self.repo.detail(b.id)['members']
        (path/'invocation.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'Calculation-time checksum'):load_bundle(path,b,members,self.root)

    def test_complete_rejects_leakage_even_with_acknowledgment(self):
        b=self.batch();self.unlock(self.l2[0]);path=f'/annotations/validation/{b.id}';self.client.get(path)
        with self.client.session_transaction() as session:csrf=session['validation_management_csrf']
        self.training['membership']['article_ids']={str(self.l2[0].article_id)}
        response=self.client.post(path,data=dict(action='complete',csrf_token=csrf,reference_quality_accepted='1'))
        self.assertIn('verification failed',response.get_data(as_text=True))
        self.assertEqual(self.repo.detail(b.id)['batch'].status,'in_review')


if __name__=='__main__':unittest.main()
