"""L2 review integration against synthetic records; no cloud or article corpus access."""
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from database.models import AutomatedAnnotation, HumanValidation
from tests import test_l2_ui


class L2HumanReviewTests(test_l2_ui.L2ReviewFixture):

    def test_direct_unlock_and_confirm_preserves_machine_and_lineage(self):
        for annotation in (self.weak, self.l2[0]):
            self.unlock(annotation)
            before = (annotation.label, annotation.confidence, annotation.evidence.copy())
            response = self.save(annotation)
            self.assertEqual(response.status_code, 303)
            self.assertEqual(parse_qs(urlsplit(response.location).query)['mode'],
                             ['weak' if annotation is self.weak else 'model'])
            with self.sessions() as session:
                review = session.scalar(select(HumanValidation).where(
                    HumanValidation.automated_annotation_id == annotation.id))
                machine = session.get(AutomatedAnnotation, annotation.id)
                self.assertEqual((machine.label, machine.confidence, machine.evidence), before)
                self.assertEqual((review.layer, review.machine_label, review.human_label),
                                 ('L2', annotation.label, annotation.label))
                self.assertEqual(review.article_version_id, annotation.article_version_id)
                self.assertEqual(review.reviewer_identity, 'configured-researcher')
                self.assertEqual(review.guideline_version, 'synthetic-test-guide')
            self.client.get(response.location)
        data = self.service.overview()['l2_human_review']
        self.assertEqual(data['weak']['counts']['L2']['confirmed'], 1)
        self.assertEqual(data['model']['counts']['L2']['confirmed'], 1)

    def test_correction_revisions_and_stale_forms(self):
        annotation = self.weak
        self.unlock(annotation)
        response = self.save(annotation, decision='corrected', human_label='gbv',
                             error_category='rule_false_negative', reason='Synthetic GBV context')
        self.assertEqual(response.status_code, 303)
        self.client.get(response.location)
        first = self.service.reviews.history(annotation.id)[0]
        response = self.save(annotation, expected=str(first.id), decision='corrected', human_label='not_gbv',
                             error_category='other', reason='Revised synthetic context')
        self.assertEqual(response.status_code, 303)
        self.client.get(response.location)
        history = self.service.reviews.history(annotation.id)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].supersedes_validation_id, first.id)
        self.assertEqual(history[1].human_label, 'gbv')
        self.assertEqual(self.save(annotation, expected=str(first.id)).status_code, 409)
        self.assertEqual(self.count(), 2)

    def test_unresolved_decisions_and_cross_layer_labels(self):
        for annotation, decision in zip(self.l2, ('unable_to_determine', 'needs_adjudication', 'confirmed')):
            self.unlock(annotation)
            response = self.save(annotation, decision=decision)
            self.assertEqual(response.status_code, 303)
            self.client.get(response.location)
            review = self.service.reviews.history(annotation.id)[0]
            self.assertEqual(review.human_label, annotation.label if decision == 'confirmed' else None)
            self.assertEqual(self.save(annotation, decision='corrected', human_label='kenya',
                                      expected=str(review.id), error_category='other', reason='Invalid layer').status_code, 422)
        self.assertEqual(self.count(), 3)

    def test_filtered_navigation_save_next_and_review_counts(self):
        query = '?mode=model&source=citizen&review_status=not_reviewed&method_version=l2-ui-model&model_version=synthetic-model-v1'
        self.unlock(self.l2[2], query)
        response = self.save(self.l2[2], query=query, action='save_next')
        self.assertEqual(response.status_code, 303)
        self.assertIn(str(self.l2[1].id), response.location)
        context = parse_qs(urlsplit(response.location).query)
        for key, value in [('mode', 'model'), ('review_status', 'not_reviewed'),
                           ('method_version', 'l2-ui-model'), ('model_version', 'synthetic-model-v1'), ('page', '1')]:
            self.assertEqual(context[key], [value])
        html = self.client.get(response.location).get_data(as_text=True)
        self.assertIn('1 / 2 in this filtered cohort', html)
        self.assertNotIn('LF_synthetic', html)
        rows, total = self.service.results('L2', {'mode': 'model', 'review_status': 'confirmed'}, 1, 20)
        self.assertEqual((total, rows[0][0].id), (1, self.l2[2].id))
        self.assertEqual(self.service.results('L2', {'mode': 'weak', 'review_status': 'confirmed'}, 1, 20)[1], 0)
        self.assertEqual(self.service.l2_label_counts({'mode': 'weak', 'review_status': 'not_reviewed'}),
                         {'gbv': 0, 'not_gbv': 0, 'borderline': 1})
        self.assertIn('L2 · Weak bootstrap Human Review', self.client.get('/annotations').get_data(as_text=True))

    def test_version_and_label_navigation_stays_in_selected_cohort(self):
        filters = {'mode': 'model', 'label': 'gbv', 'model_version': 'synthetic-model-v1'}
        neighbors = self.service.review_detail(self.l2[0].id, filters, 1)['neighbors']
        self.assertEqual((neighbors['position'], neighbors['total'], neighbors['next_id']), (1, 1, None))
        filters['model_version'] = 'different-model'
        self.assertIsNone(self.service.review_detail(self.l2[0].id, filters, 1)['neighbors']['position'])

    def test_new_machine_result_does_not_inherit_review(self):
        self.unlock(self.weak)
        response = self.save(self.weak)
        self.client.get(response.location)
        with self.sessions.begin() as session:
            old = session.get(AutomatedAnnotation, self.weak.id)
            new = AutomatedAnnotation(id=uuid4(), article_id=old.article_id, article_version_id=old.article_version_id,
                annotation_run_id=old.annotation_run_id, prerequisite_annotation_id=old.prerequisite_annotation_id,
                layer='L2', label='gbv', method_name=old.method_name, method_version=old.method_version,
                evidence={}, reason_codes=[], created_at=self.now + timedelta(days=1))
            session.add(new)
        summary = self.service.overview()['l2_human_review']
        self.assertEqual(summary['weak']['counts']['L2']['reviewed'], 0)
        self.assertEqual(summary['weak']['counts']['L2']['not_reviewed'], 1)
        self.assertEqual(summary['model']['counts']['L2']['reviewed'], 0)
        old = self.service.review_detail(self.weak.id, {'mode': 'weak'}, 1)
        self.assertIsNone(old['neighbors']['position'])
        self.assertEqual(old['current_review'].review_decision, 'confirmed')

    def test_direct_l2_access_protects_text_csrf_and_remote_writes(self):
        annotation = self.l2[1]  # Stored synthetic body includes an executable-looking tag.
        response = self.client.get(self.url(annotation))
        self.assertNotIn('private-text', response.get_data(as_text=True))
        self.objects.read_json.assert_not_called()
        self.assertEqual(self.client.post(self.url(annotation), data={'action': 'unlock', 'review_token': 'r'*40}).status_code, 403)
        self.unlock(annotation)
        html = self.client.get(self.url(annotation)).get_data(as_text=True)
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<script>window.reviewLeak', html)
        response = self.client.get(self.url(annotation), environ_overrides={'REMOTE_ADDR': '203.0.113.8'})
        self.assertNotIn('private-text', response.get_data(as_text=True))
        self.assertNotIn('Save Review', response.get_data(as_text=True))
        response = self.client.post(self.url(annotation), data={'action': 'save', 'csrf_token': self.csrf(), 'decision': 'confirmed'},
                                    environ_overrides={'REMOTE_ADDR': '203.0.113.8'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.count(), 0)

    def test_missing_l2_migration_blocks_saves_but_not_inspection(self):
        with patch.object(self.service.reviews, 'l2_available', return_value=False):
            self.unlock(self.weak)
            html = self.client.get(self.url(self.weak)).get_data(as_text=True)
            self.assertIn('Human-validation storage is unavailable', html)
            self.assertNotIn('Save Review', html)
            self.assertEqual(self.save(self.weak).status_code, 503)
            self.assertEqual(self.client.get('/annotations/l2?mode=weak&review_status=not_reviewed').status_code, 503)
            self.assertEqual(self.client.get('/annotations/l2?mode=weak').status_code, 200)
            self.assertEqual(self.client.get('/annotations').status_code, 200)
        self.assertEqual(self.count(), 0)

    def test_storage_constraints_reject_cross_layer_label(self):
        with self.assertRaises(IntegrityError), self.sessions.begin() as session:
            session.add(HumanValidation(id=uuid4(), automated_annotation_id=self.weak.id,
                article_id=self.weak.article_id, article_version_id=self.weak.article_version_id,
                layer='L2', machine_label='borderline', human_label='kenya', review_decision='corrected',
                error_category='other', review_reason='Synthetic invalid label', reviewer_identity='synthetic',
                guideline_version='synthetic', created_at=self.now))
        self.assertEqual(self.count(), 0)
