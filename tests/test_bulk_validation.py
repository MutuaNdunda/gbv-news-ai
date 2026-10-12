"""Bulk review uses synthetic pinned membership and real Flask/SQL persistence."""
import json
from copy import deepcopy
from unittest.mock import Mock, patch
from uuid import uuid4

from bs4 import BeautifulSoup
from sqlalchemy import event, select
from sqlalchemy.exc import OperationalError

from annotations.validation_batches import membership_digest
from annotations.validation import INDEPENDENT_REASONS
from database.models import Article, ArticleVersion, AutomatedAnnotation, HumanValidation, ValidationBatchMember
from database.repositories.validation_batches import ValidationBatchRepository
from tests.test_l2_ui import L2ReviewFixture


class BulkValidationFixture(L2ReviewFixture):
    def setUp(self):
        super().setUp()
        self.training = {'membership': {'article_ids': set(), 'article_version_ids': set(), 'content_hashes': set()},
            'model_version': 'synthetic-model-v1', 'method_version': 'l2-ui-model', 'manifest_sha256': 'a'*64,
            'model_manifest_sha256': 'b'*64, 'dataset_version': 'synthetic-data', 'record_count': 0}
        self.repo = ValidationBatchRepository(self.sessions, self.objects, lambda: self.service.methods(), lambda: self.training)
        self.app.extensions['validation_repository'] = self.repo

    def batch(self, name='bulk-synthetic', size=3, purpose='development_validation', freeze=True):
        preview = self.repo.preview(name, purpose, 3, 'random', 42, 'synthetic-test-guide')
        if size > 3:
            with self.sessions.begin() as db:
                base = db.get(ArticleVersion, self.l2[0].article_version_id)
                for index in range(3, size):
                    version = ArticleVersion(**{c.name: getattr(base, c.name) for c in ArticleVersion.__table__.columns})
                    version.id = uuid4(); version.content_hash = f'{index:064x}'
                    annotation = AutomatedAnnotation(**{c.name: getattr(self.l2[0], c.name) for c in AutomatedAnnotation.__table__.columns})
                    annotation.id = uuid4(); annotation.article_version_id = version.id
                    db.add(version); db.flush(); db.add(annotation); db.flush()
                    item = deepcopy(next(r for r in preview['selected'] if r['annotation_id'] == self.l2[0].id))
                    item.update(id=version.id, content_hash=version.content_hash, annotation_id=annotation.id)
                    preview['selected'].append(item)
            preview['size'] = size
            preview['configuration']['membership_sha256'] = membership_digest(preview['selected'])
        batch = self.repo.create(preview)
        if freeze: self.repo.freeze(batch.id)
        return batch

    def path(self, batch): return f'/annotations/validation/{batch.id}/bulk'

    def open_bulk(self, batch):
        self.unlock(self.l2[0]); self.objects.read_json.reset_mock()
        return self.client.get(self.path(batch))

    def bulk_csrf(self):
        with self.client.session_transaction() as session: return session['validation_bulk_csrf']

    def body(self, batch, member):
        return self.client.get(f'{self.path(batch)}/{member.id}/body')

    def decision(self, member, choice='gbv', receipt='', expected=''):
        return dict(member_id=str(member.id), choice=choice, reason='Synthetic independent context rationale',
                    expected_final=expected, body_receipt=receipt)

    def submit(self, batch, rows):
        return self.client.post(self.path(batch)+'/save', data={
            'csrf_token': self.bulk_csrf(), 'decisions': json.dumps(rows, ensure_ascii=False)})


class BulkValidationTests(BulkValidationFixture):
    def test_reason_dropdown_and_optional_details_save_without_changing_verdict(self):
        batch = self.batch(); response = self.open_bulk(batch)
        members = self.repo.detail(batch.id)['members']
        soup = BeautifulSoup(response.data, 'html.parser')
        category = soup.select_one('.bulk-reason-category')
        self.assertFalse(category.has_attr('required'))  # Unselected bulk rows must not block the form.
        self.assertEqual([option['value'] for option in category.select('option')][1:], list(INDEPENDENT_REASONS))
        for index, (key, label) in enumerate(INDEPENDENT_REASONS.items()):
            member = self.repo.member(batch.id, members[0].id)['member']
            row = self.decision(member, 'not_gbv', expected=str(member.final_human_validation_id or ''))
            row.update(reason_category=key, reason_details='Synthetic context' if index % 2 else '',
                       reason='Ignored legacy text')
            result = self.submit(batch, [row]).json
            self.assertEqual((result['saved'], result['failed']), (1, 0))
            member = self.repo.member(batch.id, member.id)['member']
            with self.sessions() as db:
                review = db.get(HumanValidation, member.final_human_validation_id)
                self.assertEqual(review.review_reason, label + (' — Synthetic context' if index % 2 else ''))
                self.assertEqual(review.human_label, 'not_gbv')
        row = self.decision(members[1], 'gbv')
        for category, details in [('', ''), ('invented', ''), (None, ''), ('other', None), ('other', 'x'*901)]:
            row.update(reason_category=category, reason_details=details)
            self.assertEqual(self.submit(batch, [row]).json['failed'], 1)
        self.assertEqual(self.count(), len(INDEPENDENT_REASONS))

    def test_single_article_reason_selection_and_error_retention(self):
        batch = self.batch(); self.open_bulk(batch); member = self.repo.detail(batch.id)['members'][0]
        url = f'/annotations/review/{member.automated_annotation_id}?batch_id={batch.id}&member_id={member.id}'
        html = self.client.get(url)
        soup = BeautifulSoup(html.data, 'html.parser')
        self.assertTrue(soup.select_one('[name=reason_category]').has_attr('required'))
        with self.client.session_transaction() as session:
            csrf = session['human_review_csrf']
        form = dict(action='save', csrf_token=csrf, choice='not_gbv', expected_final='',
                    reason_category='sports_news', reason_details='Synthetic sports context')
        invalid = dict(form, reason_details='x'*901)
        response = self.client.post(url, data=invalid)
        self.assertEqual(response.status_code, 422)
        soup = BeautifulSoup(response.data, 'html.parser')
        self.assertEqual(soup.select_one('[name=reason_category] option[selected]')['value'], 'sports_news')
        self.assertEqual(soup.select_one('[name=reason_details]').text, 'x'*901)
        self.assertEqual(self.client.post(url, data=form).status_code, 303)
        with self.sessions() as db:
            review = db.scalar(select(HumanValidation))
            self.assertEqual(review.review_reason, 'Sports news — Synthetic sports context')

    def test_review_status_shows_latest_reviewer_verdict_and_unreviewed_members(self):
        batch = self.batch(purpose='final_test'); response = self.open_bulk(batch)
        members = self.repo.detail(batch.id)['members']
        soup = BeautifulSoup(response.data, 'html.parser')
        for card in soup.select('[data-member-id]'):
            self.assertEqual(card.select_one('.bulk-review-status').text, 'Article not reviewed')
            self.assertTrue(card.select_one('.bulk-review-details').has_attr('hidden'))
        result = self.submit(batch, [self.decision(members[0], 'not_gbv')]).json['results'][0]
        self.assertEqual(result['reviewer_identity'], 'configured-researcher')
        self.repo.save_decision(batch.id, members[0].id, 'needs_adjudication',
            'Synthetic independent revision', '<Synthetic second reviewer>', 'synthetic-test-guide', result['final_id'])
        response = self.client.get(self.path(batch) + '?status=all')
        soup = BeautifulSoup(response.data, 'html.parser')
        card = soup.select_one(f'[data-member-id="{members[0].id}"]')
        self.assertEqual(card.select_one('.bulk-review-status').text, 'Article reviewed')
        self.assertFalse(card.select_one('.bulk-review-details').has_attr('hidden'))
        self.assertEqual(card.select_one('.bulk-reviewer').text, '<Synthetic second reviewer>')
        self.assertEqual(card.select_one('.bulk-saved-choice').text, 'Needs adjudication')
        self.assertIsNone(card.find('synthetic'))
        body = self.body(batch, members[0]).json
        self.assertEqual(body['reviewer_identity'], '<Synthetic second reviewer>')
        self.assertEqual(body['human_choice'], 'needs_adjudication')
        for member, expected_status, expected_verdict in (
                (members[0], 'Article reviewed', 'Needs adjudication'),
                (members[1], 'Article not reviewed', '')):
            path = f'/annotations/review/{member.automated_annotation_id}?batch_id={batch.id}&member_id={member.id}'
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            summary = BeautifulSoup(response.data, 'html.parser').select_one('.validation-review-summary')
            self.assertEqual(summary.select_one('.bulk-review-status').text, expected_status)
            self.assertEqual(summary.select_one('.bulk-saved-choice').text, expected_verdict)
            self.assertNotIn('Machine label:', response.get_data(as_text=True))
        self.assertNotIn('gbv_probability', soup.get_text())

    def test_headlines_page_sizes_sql_pagination_and_no_body_reads(self):
        batch = self.batch(size=123)
        self.open_bulk(batch)
        for size in (10, 20, 50, 100):
            response = self.client.get(self.path(batch)+f'?per_page={size}')
            soup = BeautifulSoup(response.data, 'html.parser')
            self.assertEqual(len(soup.select('[data-member-id]')), size)
            self.assertIn('Synthetic article', soup.select_one('.bulk-headline').text)
            self.assertIn('Language metadata', response.get_data(as_text=True))
        second = self.client.get(self.path(batch)+'?per_page=100&page=2')
        self.assertEqual(len(BeautifulSoup(second.data, 'html.parser').select('[data-member-id]')), 23)
        for query in ('per_page=999', 'page=-1', 'status=model_positive'):
            self.assertEqual(self.client.get(self.path(batch)+'?'+query).status_code, 400)
        self.objects.read_json.assert_not_called()

    def test_page_query_count_bounded_independent_of_page_size(self):
        batch = self.batch(size=123); self.open_bulk(batch)
        counts = []
        for size in (10, 100):
            queries = []
            def capture(*args): queries.append(args[2])
            event.listen(self.engine, 'before_cursor_execute', capture)
            try: self.client.get(self.path(batch)+f'?per_page={size}')
            finally: event.remove(self.engine, 'before_cursor_execute', capture)
            counts.append(len(queries))
        self.assertEqual(counts[0], counts[1])
        self.assertLess(counts[0], 20)

    def test_blind_body_is_lazy_private_escaped_and_batch_scoped(self):
        batch = self.batch(); response = self.open_bulk(batch)
        member = self.repo.detail(batch.id)['members'][0]
        self.objects.read_json.assert_not_called()
        body = self.body(batch, member)
        self.assertEqual(body.status_code, 200)
        self.assertTrue(body.json['body_receipt'])
        self.assertIn('Synthetic article', body.json['article_text'])
        self.assertEqual(body.headers['Cache-Control'], 'private, no-store')
        self.assertEqual(set(body.json), {'title', 'article_text', 'content_issue', 'body_receipt', 'expected_final', 'human_choice', 'reviewer_identity'})
        self.assertIsNone(body.json['reviewer_identity'])
        for forbidden in ('gbv_probability', 'positive_threshold', 'synthetic_prediction', 'Machine label:', 'l2-ui-model'):
            self.assertNotIn(forbidden, response.get_data(as_text=True))
            self.assertNotIn(forbidden, body.get_data(as_text=True))
        self.assertEqual(self.client.get(f'/annotations/validation/{uuid4()}/bulk/{member.id}/body').status_code, 404)
        self.assertEqual(self.client.get(f'{self.path(batch)}/{uuid4()}/body').status_code, 404)

    def test_bulk_save_preserves_lineage_initial_pointer_history_and_notes(self):
        batch = self.batch(); self.open_bulk(batch)
        members = self.repo.detail(batch.id)['members']
        before = [(m.id, m.article_version_id, m.content_hash) for m in members]
        rows = [self.decision(m, receipt=self.body(batch, m).json['body_receipt']) for m in members]
        result = self.submit(batch, rows).json
        self.assertEqual((result['saved'], result['failed']), (3, 0))
        self.assertEqual(result['progress'], {'total': 3, 'reviewed': 3, 'pending': 0})
        after = self.repo.detail(batch.id)['members']
        self.assertEqual(before, [(m.id, m.article_version_id, m.content_hash) for m in after])
        with self.sessions() as db:
            reviews = db.scalars(select(HumanValidation)).all()
            self.assertEqual(len(reviews), 3)
            self.assertTrue(all(r.reviewer_identity == 'configured-researcher' for r in reviews))
            self.assertTrue(all(r.guideline_version == 'synthetic-test-guide' for r in reviews))
            self.assertTrue(all(r.notes == 'Bulk review: verified body opened.' for r in reviews))
        member = after[0]; initial = member.initial_human_validation_id
        receipt = self.body(batch, member).json['body_receipt']
        result = self.submit(batch, [self.decision(member, 'not_gbv', receipt, str(member.final_human_validation_id))]).json
        self.assertEqual(result['saved'], 1)
        revised = self.repo.member(batch.id, member.id)['member']
        self.assertEqual(revised.initial_human_validation_id, initial)
        self.assertNotEqual(revised.final_human_validation_id, initial)
        with self.sessions() as db:
            revision = db.get(HumanValidation, revised.final_human_validation_id)
            self.assertEqual(revision.supersedes_validation_id, initial)

    def test_partial_errors_skip_and_saved_vs_unsaved_progress(self):
        batch = self.batch(); self.open_bulk(batch); members = self.repo.detail(batch.id)['members']
        rows = [self.decision(members[0], 'unable_to_determine'), self.decision(members[1], 'gbv'), self.decision(members[2], 'skip')]
        rows[1]['reason'] = ''
        result = self.submit(batch, rows).json
        self.assertEqual((result['saved'], result['failed']), (1, 1))
        self.assertEqual(result['results'][2]['status'], 'skipped')
        self.assertEqual(result['progress'], {'total': 3, 'reviewed': 1, 'pending': 2})
        with self.sessions() as db:
            review = db.scalar(select(HumanValidation))
            self.assertIsNone(review.human_label)
            self.assertIn('body not opened', review.notes)
        page = self.client.get(self.path(batch))
        soup = BeautifulSoup(page.data, 'html.parser')
        self.assertEqual(len(soup.select('[data-member-id]')), 2)
        self.assertEqual(soup.select_one('#bulk-unsaved').text, '0')

    def test_duplicate_retries_and_concurrent_reviews_do_not_append_twice(self):
        batch = self.batch(); self.open_bulk(batch); member = self.repo.detail(batch.id)['members'][0]
        row = self.decision(member, 'unable_to_determine')
        self.assertEqual(self.submit(batch, [row]).json['saved'], 1)
        result = self.submit(batch, [row]).json
        self.assertEqual(result['results'][0]['status'], 'conflict')
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.submit(batch, [row, row]).status_code, 400)
        body = self.body(batch, member).json
        self.assertTrue(body['expected_final'])
        self.assertEqual(body['human_choice'], 'unable_to_determine')

    def test_body_receipt_cannot_be_reused_for_another_member_or_revision(self):
        batch = self.batch(); self.open_bulk(batch); members = self.repo.detail(batch.id)['members']
        receipt = self.body(batch, members[0]).json['body_receipt']
        result = self.submit(batch, [self.decision(members[1], receipt=receipt)]).json
        self.assertEqual(result['results'][0]['status'], 'conflict')
        self.assertEqual(self.count(), 0)
        self.submit(batch, [self.decision(members[0], receipt=receipt)])
        member = self.repo.member(batch.id, members[0].id)['member']
        result = self.submit(batch, [self.decision(member, 'not_gbv', receipt, str(member.final_human_validation_id))]).json
        self.assertEqual(result['results'][0]['status'], 'conflict')
        self.assertEqual(self.count(), 1)

    def test_title_only_resolved_labels_save_without_loading_bodies(self):
        batch = self.batch(); self.open_bulk(batch); members = self.repo.detail(batch.id)['members']
        rows = [self.decision(member, choice) for member, choice in
                zip(members, ('gbv', 'not_gbv', 'borderline'))]
        result = self.submit(batch, rows).json
        self.assertEqual((result['saved'], result['failed']), (3, 0))
        self.objects.read_json.assert_not_called()
        with self.sessions() as db:
            reviews = list(db.scalars(select(HumanValidation)))
            self.assertEqual({review.human_label for review in reviews}, {'gbv', 'not_gbv', 'borderline'})
            for review in reviews:
                self.assertEqual(review.notes, 'Bulk review: title-only decision; verified body not opened.')
        member = self.repo.member(batch.id, members[0].id)['member']
        result = self.submit(batch, [self.decision(member, 'not_gbv', expected=str(member.final_human_validation_id))]).json
        self.assertEqual(result['saved'], 1)
        revised = self.repo.member(batch.id, member.id)['member']
        self.assertEqual(revised.initial_human_validation_id, member.initial_human_validation_id)
        self.assertNotEqual(revised.final_human_validation_id, member.final_human_validation_id)

    def test_unverified_body_allows_title_only_and_uncertainty(self):
        batch = self.batch(); self.open_bulk(batch); member = self.repo.detail(batch.id)['members'][0]
        with patch.object(self.service, 'review_content', return_value={'article_text': None, 'content_issue': 'Cannot verify extraction'}):
            body = self.body(batch, member).json
        self.assertIsNone(body['body_receipt'])
        self.assertEqual(self.submit(batch, [self.decision(member)]).json['saved'], 1)
        member = self.repo.member(batch.id, member.id)['member']
        self.assertEqual(self.submit(batch, [self.decision(member, 'needs_adjudication',
            expected=str(member.final_human_validation_id))]).json['saved'], 1)

    def test_invalid_vocabulary_reason_wrong_member_and_guideline_fail(self):
        batch = self.batch(); self.open_bulk(batch); members = self.repo.detail(batch.id)['members']
        row = self.decision(members[0], 'confirmed')
        self.assertEqual(self.submit(batch, [row]).json['failed'], 1)
        row.update(choice='unable_to_determine', reason='')
        self.assertEqual(self.submit(batch, [row]).json['failed'], 1)
        row.update(reason='x'*1001)
        self.assertEqual(self.submit(batch, [row]).json['failed'], 1)
        row.update(member_id=str(uuid4()), reason='Synthetic')
        self.assertEqual(self.submit(batch, [row]).json['failed'], 1)
        with self.sessions.begin() as db:
            from database.models import ValidationBatch
            db.get(ValidationBatch, batch.id).guideline_version = 'different-codebook'
        self.assertEqual(self.submit(batch, [self.decision(members[0], 'unable_to_determine')]).json['failed'], 1)
        self.assertEqual(self.count(), 0)

    def test_bounds_malformed_payload_and_server_failures_have_no_sql_leak(self):
        batch = self.batch(); self.open_bulk(batch); member = self.repo.detail(batch.id)['members'][0]
        for rows in ([], {}, [1]):
            self.assertEqual(self.submit(batch, rows).status_code, 400)
        self.assertEqual(self.submit(batch, [self.decision(member)]*101).status_code, 400)
        response = self.client.post(self.path(batch)+'/save', data={'csrf_token': self.bulk_csrf(), 'decisions': 'x'*1200001})
        self.assertEqual(response.status_code, 413)
        error = OperationalError('private SQL', {}, Exception('private credential'))
        with patch.object(self.repo, '_append_decision', side_effect=error):
            response = self.submit(batch, [self.decision(member, 'unable_to_determine')])
        self.assertEqual(response.json['failed'], 1)
        self.assertNotIn('private SQL', response.get_data(as_text=True))
        self.assertNotIn('private credential', response.get_data(as_text=True))

    def test_one_hundred_decisions_fit_endpoint_limit_and_persist(self):
        batch = self.batch(size=123); self.open_bulk(batch)
        members = self.repo.detail(batch.id)['members'][:100]
        rows = [self.decision(m, 'unable_to_determine') for m in members]
        for row in rows: row['reason'] = 'Synthetic ' + '語'*990
        response = self.submit(batch, rows)
        self.assertEqual(response.status_code, 200)
        self.assertEqual((response.json['saved'], response.json['failed']), (100, 0))
        self.assertEqual(response.json['progress']['pending'], 23)

    def test_bulk_save_prefetch_selects_do_not_grow_per_member(self):
        batch = self.batch(size=123); self.open_bulk(batch)
        members = self.repo.detail(batch.id)['members']
        counts = []
        for group in (members[:10], members[10:110]):
            queries = []
            def capture(*args):
                if args[2].lstrip().upper().startswith('SELECT'): queries.append(args[2])
            event.listen(self.engine, 'before_cursor_execute', capture)
            try: response = self.submit(batch, [self.decision(m, 'unable_to_determine') for m in group])
            finally: event.remove(self.engine, 'before_cursor_execute', capture)
            self.assertEqual(response.json['saved'], len(group))
            counts.append(len(queries))
        self.assertEqual(counts[0], counts[1])

    def test_whole_transaction_failure_reports_no_success_and_leaks_no_sql(self):
        batch = self.batch(); self.open_bulk(batch); member = self.repo.detail(batch.id)['members'][0]
        error = OperationalError('private SQL', {}, Exception('private credential'))
        with patch.object(self.repo, 'save_bulk_decisions', side_effect=error):
            response = self.submit(batch, [self.decision(member, 'unable_to_determine')])
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private SQL', response.get_data(as_text=True))
        self.assertNotIn('results', response.json)
        self.assertEqual(self.count(), 0)

    def test_receipt_tamper_and_expiry_require_reopening(self):
        from itsdangerous import SignatureExpired
        batch = self.batch(); self.open_bulk(batch); member = self.repo.detail(batch.id)['members'][0]
        receipt = self.body(batch, member).json['body_receipt']
        result = self.submit(batch, [self.decision(member, receipt=receipt+'tampered')]).json
        self.assertEqual(result['failed'], 1)
        signer = Mock()
        signer.loads.side_effect = SignatureExpired('expired')
        with patch('app.routes.validation.body_signer', return_value=signer):
            result = self.submit(batch, [self.decision(member, receipt=receipt)]).json
        self.assertEqual(result['failed'], 1)
        self.assertEqual(self.count(), 0)

    def test_authorization_csrf_remote_and_expiry_block_all_endpoints(self):
        batch = self.batch(); self.open_bulk(batch); member = self.repo.detail(batch.id)['members'][0]
        paths = [self.path(batch), f'{self.path(batch)}/{member.id}/body']
        for path in paths:
            self.assertEqual(self.client.get(path, environ_overrides={'REMOTE_ADDR': '203.0.113.5'}).status_code, 403)
            self.assertEqual(self.client.get(path, headers={'Forwarded': 'for=203.0.113.5'}).status_code, 403)
        response = self.client.post(self.path(batch)+'/save', data={'csrf_token': 'bad', 'decisions': '[]'})
        self.assertEqual(response.status_code, 403)
        with self.client.session_transaction() as session: session['human_review_started'] = 0
        self.assertEqual(self.body(batch, member).status_code, 401)
        self.assertEqual(self.submit(batch, [self.decision(member, 'unable_to_determine')]).status_code, 401)
        self.assertEqual(self.count(), 0)

    def test_filters_resume_and_completed_read_only_without_feedback(self):
        batch = self.batch(purpose='final_test'); self.open_bulk(batch)
        members = self.repo.detail(batch.id)['members']
        self.submit(batch, [self.decision(members[0], 'needs_adjudication')])
        self.assertEqual(len(self.repo.bulk_page(batch.id, status='reviewed')['rows']), 1)
        self.assertEqual(len(self.repo.bulk_page(batch.id, status='needs_adjudication')['rows']), 1)
        self.assertEqual(len(self.repo.bulk_page(batch.id, status='all')['rows']), 3)
        first = self.repo.bulk_page(batch.id)['rows'][0]
        self.assertEqual(first['id'], members[1].id)
        self.submit(batch, [self.decision(m, 'unable_to_determine') for m in members[1:]])
        self.repo.complete(batch.id)
        html = self.client.get(self.path(batch)+'?status=all').get_data(as_text=True)
        self.assertNotIn('data-choice=', html)
        self.assertNotIn('gbv_probability', html)
        self.assertNotIn('confirmed', html)
        self.assertEqual(self.submit(batch, [self.decision(members[1], 'gbv')]).json['saved'], 0)

    def test_draft_missing_batch_and_missing_schema_fail_closed(self):
        batch = self.batch(freeze=False); self.open_bulk(batch)
        self.assertEqual(self.client.get(self.path(batch)).status_code, 409)
        self.assertEqual(self.client.get(f'/annotations/validation/{uuid4()}/bulk').status_code, 404)
        with patch.object(self.repo, 'available', return_value=False):
            self.assertEqual(self.client.get(self.path(batch)).status_code, 503)
