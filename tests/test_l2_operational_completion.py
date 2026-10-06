"""Schema refusal, sleep prevention, fail-closed leases and append-only partial resume."""
from contextlib import nullcontext
from copy import deepcopy
import unittest
from unittest.mock import Mock, patch

from sqlalchemy.exc import OperationalError
from annotations.schemas import AnnotationResult, DEFAULT_CONFIG
from annotations.l2_config import MODEL_METHOD, L2Config
from annotations.service import failure_details, run_annotation_pipeline
from database.repositories.annotations import AnnotationLease, AnnotationLockLost, AnnotationRepository
from scripts.run_annotations import prevent_idle_sleep
from tests.test_l2_pipeline import L2Repository
from tests.test_annotation_pipeline import candidate
from tests.test_annotation_rules import valid_article


class L2OperationalTests(unittest.TestCase):
    def setUp(self):
        self.items = [candidate(), candidate()]
        self.repository = L2Repository(self.items)
        self.objects = Mock(buckets={'processed': 'processed'})
        self.objects.read_json.return_value = valid_article()
        self.predictor = Mock(method_name=MODEL_METHOD, method_version='l2-existing-model')
        self.predictor.predict_batch.side_effect = lambda articles: [self.result() for _ in articles]
        for item in self.items:
            self.upstream(item)

    def result(self):
        return AnnotationResult('L2', 'not_gbv', MODEL_METHOD, 'l2-existing-model', .1)

    def upstream(self, item):
        l0 = self.repository.persist(item, None, AnnotationResult('L0', 'valid', 'synthetic', DEFAULT_CONFIG.method_version('L0')))
        return self.repository.persist(item, None, AnnotationResult('L1', 'kenya', 'kenya_relevance_hybrid', DEFAULT_CONFIG.method_version('L1')), l0.id)

    def run_model(self):
        return run_annotation_pipeline(['L2'], services=(self.repository, self.objects),
                                       l2_predictor=self.predictor, l2_config=L2Config())

    def test_missing_schema_refused_before_run_or_result_writes(self):
        before = list(self.repository.results)
        self.repository.ensure_l2_schema = Mock(side_effect=RuntimeError('L2 schema is not ready'))
        with self.assertRaisesRegex(RuntimeError, 'schema is not ready'):
            self.run_model()
        self.assertEqual(self.repository.runs, {})
        self.assertEqual(self.repository.results, before)
        self.objects.read_json.assert_not_called()

    def test_repository_requires_all_installed_schema_checks(self):
        repository = AnnotationRepository(Mock())
        for ready in (False, True):
            with patch('annotations.l2_readiness.l2_schema_readiness', return_value={
                    'ready_for_prediction_writes': ready, 'missing': [] if ready else ['l2_label_constraint']}):
                if ready:
                    repository.ensure_l2_schema()
                else:
                    with self.assertRaisesRegex(RuntimeError, 'l2_label_constraint'):
                        repository.ensure_l2_schema()

    def test_transient_persistence_failure_records_phase_and_resumes_without_retry(self):
        original = self.repository.persist
        calls = []
        failure = OperationalError('PRIVATE SQL', {'password': 'PRIVATE'}, RuntimeError('PRIVATE driver'), connection_invalidated=True)
        def persist(*args):
            calls.append(args[0]['id'])
            if len(calls) == 1:
                raise failure
            return original(*args)
        self.repository.persist = persist
        first = self.run_model()
        first_snapshot = deepcopy(first)
        self.assertEqual((first['success'], first['failed']), (1, 1))
        self.assertEqual(first['errors'][0]['failure_phase'], 'prediction_persistence')
        self.assertTrue(first['errors'][0]['connection_invalidated'])
        self.assertEqual(len(calls), 2)  # no automatic replay of failed/uncertain writes
        existing = self.repository.results[-1]
        second = self.run_model()
        self.assertEqual((second['requested'], second['success'], second['failed']), (1, 1, 0))
        self.assertIn(existing, self.repository.results)
        self.assertEqual(len([r for r in self.repository.results if r.layer == 'L2']), 2)
        self.assertEqual(first, first_snapshot)
        self.assertNotIn('PRIVATE', str(first))

    def test_300_existing_predictions_retained_and_only_24_pending_processed(self):
        self.repository = L2Repository([candidate() for _ in range(324)])
        for index, item in enumerate(self.repository.candidates):
            l1 = self.upstream(item)
            if index < 300:
                self.repository.persist(item, None, self.result(), l1.id)
        before = [vars(row).copy() for row in self.repository.results]
        run = self.run_model()
        self.assertEqual((run['requested'], run['success'], run['failed']), (24, 24, 0))
        self.assertEqual([vars(row) for row in self.repository.results[:len(before)]], before)
        l2 = [row for row in self.repository.results if row.layer == 'L2']
        self.assertEqual(len(l2), 324)
        self.assertEqual(len({(row.article_version_id, row.method_version, row.prerequisite_annotation_id) for row in l2}), 324)
        self.assertEqual(self.run_model()['requested'], 0)
        self.assertTrue(all(run['configuration']['only_pending'] for run in self.repository.runs.values()))

    def test_lock_loss_before_second_persist_keeps_first_and_stops_subsequent_writes(self):
        lease = Mock()
        persisted = []
        original = self.repository.persist
        def persist(*args):
            persisted.append(args[0]['id'])
            return original(*args)
        self.repository.persist = persist
        def check():
            if persisted:
                raise AnnotationLockLost('lost lease')
        lease.check.side_effect = check
        self.repository.lock = Mock(return_value=nullcontext(lease))
        with self.assertRaises(AnnotationLockLost):
            self.run_model()
        self.assertEqual(len(persisted), 1)
        run = next(iter(self.repository.runs.values()))
        self.assertEqual(run['summary']['success'], 1)
        self.assertEqual(run['summary']['errors'][-1]['failure_phase'], 'lock_health_check')

    def test_same_backend_without_actual_lock_is_rejected(self):
        connection = Mock()
        connection.execute.return_value.one.return_value = (123, False)
        lease = AnnotationLease(connection, 123)
        with self.assertRaises(AnnotationLockLost):
            lease.check()
        self.assertTrue(lease.lost)
        self.assertIn('pg_locks', str(connection.execute.call_args.args[0]))

    def test_lost_connection_is_invalidated_and_no_new_lock_is_acquired(self):
        connection = Mock()
        connection.execute.side_effect = OperationalError('synthetic', {}, RuntimeError('disconnect'), connection_invalidated=True)
        lease = AnnotationLease(connection, 123)
        with self.assertRaises(AnnotationLockLost):
            lease.check()
        self.assertTrue(lease.lost)
        connection.invalidate.assert_called_once()
        connection.execute.assert_called_once()

    def test_safe_sqlstate_diagnostic_does_not_copy_driver_text(self):
        driver = RuntimeError('PRIVATE article SQL credentials')
        driver.sqlstate = '08006'
        error = OperationalError('PRIVATE', {'password': 'PRIVATE'}, driver, connection_invalidated=True)
        self.assertEqual(failure_details(error, 'prediction_persistence'), {
            'error_type': 'OperationalError', 'failure_phase': 'prediction_persistence',
            'sqlstate': '08006', 'connection_invalidated': True})

    def test_macos_idle_sleep_guard_scoped_and_cleanup_on_failure(self):
        for failure in (False, True):
            process = Mock()
            process.poll.return_value = None
            with patch('scripts.run_annotations.sys.platform', 'darwin'), patch('scripts.run_annotations.subprocess.Popen', return_value=process) as start:
                if failure:
                    with self.assertRaisesRegex(RuntimeError, 'synthetic failure'):
                        with prevent_idle_sleep(True):
                            raise RuntimeError('synthetic failure')
                else:
                    with prevent_idle_sleep(True):
                        pass
            self.assertEqual(start.call_args.args[0][:3], ['/usr/bin/caffeinate', '-i', '-w'])
            process.terminate.assert_called_once()
            process.wait.assert_called_once_with(timeout=5)

    def test_sleep_guard_unused_off_macos_or_without_model(self):
        for enabled, platform in ((True, 'linux'), (False, 'darwin')):
            with patch('scripts.run_annotations.sys.platform', platform), patch('scripts.run_annotations.subprocess.Popen') as start:
                with prevent_idle_sleep(enabled):
                    pass
                start.assert_not_called()

    def test_failed_sleep_guard_refuses_execution(self):
        process = Mock()
        process.poll.return_value = 1
        with patch('scripts.run_annotations.sys.platform', 'darwin'), patch('scripts.run_annotations.subprocess.Popen', return_value=process):
            with self.assertRaisesRegex(RuntimeError, 'prevent idle sleep'):
                with prevent_idle_sleep(True):
                    self.fail('Ran despite failed sleep guard')


if __name__ == '__main__':
    unittest.main()
