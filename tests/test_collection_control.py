"""Executed synthetic SQL/UI tests plus offline collector lifecycle regressions."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import unittest
import signal
from unittest.mock import Mock, MagicMock, patch
from uuid import uuid4

from sqlalchemy import Column, JSON, MetaData, Table, create_engine, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError

from app import create_app
from app.services.run_service import RunService, run_liveness
from collection.lifecycle import WorkerControl, CollectionStop, managed_collection, bind_run, terminal_status
from database.models import CollectionRun, CollectionRunScan, ArticleVersion
from database.repositories.collection_runs import CollectionRunRepository, CollectionLockBusy, CollectionLockLost
from scripts import trial_scraper, collect_monthly
from storage.persistence import CollectionPersistence
from tests.storage_fakes import FakeObjects, FakeArticles, FakeRuns, FakeScans

NOW = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)


class CollectionControlSQLTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://')
        with self.engine.begin() as connection:
            connection.execute(text("ATTACH DATABASE ':memory:' AS public"))
            for model in (CollectionRun, CollectionRunScan, ArticleVersion):
                table = Table(model.__tablename__, MetaData(), *(
                    Column(c.name, JSON() if isinstance(c.type, JSONB) else c.type)
                    for c in model.__table__.columns), schema='public')
                table.create(connection)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.repo = CollectionRunRepository(self.sessions)
        self.service = RunService(self.sessions)
        self.ids = {}
        with self.sessions.begin() as session:
            for index, status in enumerate(('running', 'completed', 'failed', 'interrupted', 'running')):
                value = uuid4()
                self.ids[index] = value
                session.add(CollectionRun(id=value, run_name=f'run-{index}', status=status,
                    configuration={}, started_at=NOW + timedelta(minutes=index), created_at=NOW,
                    last_heartbeat_at=NOW - timedelta(hours=2), worker_token=uuid4()))
            session.add(ArticleVersion(id=uuid4(), collection_run_id=self.ids[0]))
            session.add(CollectionRunScan(id=uuid4(), collection_run_id=self.ids[0],
                source='citizen', capture_month=NOW.date(), status='running',
                articles_saved=5, fetch_attempts=7))

    def tearDown(self):
        self.engine.dispose()

    def test_filters_counts_and_newest_first_pagination_execute_in_sql(self):
        rows, total = self.service.list(per_page=2)
        self.assertEqual(total, 5)
        self.assertEqual([row[0].id for row in rows], [self.ids[4], self.ids[3]])
        rows, total = self.service.list(page=2, per_page=1, status='running')
        self.assertEqual(total, 2)
        self.assertEqual(rows[0][0].id, self.ids[0])
        self.assertEqual(rows[0][1], 1)
        rows, total = self.service.list(status='completed')
        self.assertEqual(total, 1)
        self.assertEqual(rows[0][0].status, 'completed')
        self.assertEqual(self.service.list(status="'; DROP TABLE collection_runs")[1], 5)

    def test_stop_is_idempotent_and_only_records_intent(self):
        value = self.ids[0]
        self.assertEqual(self.repo.request_stop(value), 'requested')
        before = self.repo.control(value)
        self.assertEqual(before.status, 'running')
        self.assertIsNone(before.finished_at)
        self.assertEqual(self.repo.request_stop(value), 'already_requested')
        self.assertEqual(self.repo.control(value).stop_requested_at, before.stop_requested_at)
        for index in (1, 2, 3):
            self.assertEqual(self.repo.request_stop(self.ids[index]), 'inactive')
            self.assertIsNone(self.repo.control(self.ids[index]).stop_requested_at)
        self.assertEqual(self.repo.request_stop(uuid4()), 'missing')

    def test_legacy_worker_stop_is_not_falsely_promised(self):
        with self.sessions.begin() as session:
            session.get(CollectionRun, self.ids[0]).worker_token = None
        self.assertEqual(self.repo.request_stop(self.ids[0]), 'unsupported')
        self.assertIsNone(self.repo.control(self.ids[0]).stop_requested_at)

    def test_heartbeat_fences_old_attempt(self):
        value = self.ids[0]
        self.repo.heartbeat(value, self.repo.control(value).worker_token, NOW)
        self.assertEqual(self.repo.control(value).last_heartbeat_at, NOW.replace(tzinfo=None))
        with self.assertRaises(CollectionLockLost):
            self.repo.heartbeat(value, uuid4(), NOW)
        with self.assertRaises(CollectionLockLost):
            self.repo.set_status(value, 'interrupted', worker_token=uuid4())
        self.assertEqual(self.repo.control(value).status, 'running')

    def lock_probe(self, busy=False, callback=None):
        @contextmanager
        def lock(name):
            if busy:
                raise CollectionLockBusy()
            if callback:
                callback(name)
            yield Mock()
        return lock

    def test_stale_no_owner_reconciliation_preserves_counters_and_is_idempotent(self):
        with patch.object(self.repo, 'lock', self.lock_probe()):
            diagnostic = self.repo.reconcile_stale_runs(now=NOW)
            self.assertEqual({item['action'] for item in diagnostic}, {'would_interrupt'})
            self.assertEqual(self.repo.control(self.ids[0]).status, 'running')
            repaired = self.repo.reconcile_stale_runs(apply=True, now=NOW)
            self.assertEqual({item['action'] for item in repaired}, {'interrupted'})
            self.assertEqual(self.repo.reconcile_stale_runs(apply=True, now=NOW), [])
        row = self.repo.control(self.ids[0])
        self.assertEqual(row.finalization_reason, 'stale_run_reconciled')
        self.assertEqual(row.finished_at, NOW.replace(tzinfo=None))
        with self.sessions() as session:
            scan = session.execute(select(CollectionRunScan)).scalar_one()
            self.assertEqual((scan.articles_saved, scan.fetch_attempts), (5, 7))
            self.assertEqual(scan.status, "pending")
        for index, status in ((1, 'completed'), (2, 'failed'), (3, 'interrupted')):
            self.assertEqual(self.repo.control(self.ids[index]).status, status)

    def test_stale_active_owner_is_not_repaired(self):
        with patch.object(self.repo, 'lock', self.lock_probe(busy=True)):
            results = self.repo.reconcile_stale_runs(apply=True, now=NOW)
        self.assertTrue(all(item['ownership'] == 'active_lock' for item in results))
        self.assertEqual(self.repo.control(self.ids[0]).status, 'running')

    def test_fresh_and_missing_heartbeats_remain_running(self):
        with self.sessions.begin() as session:
            session.get(CollectionRun, self.ids[0]).last_heartbeat_at = NOW
            session.get(CollectionRun, self.ids[4]).last_heartbeat_at = None
        with patch.object(self.repo, 'lock', self.lock_probe()):
            result = self.repo.reconcile_stale_runs(apply=True, now=NOW)
        self.assertTrue(all(item['action'] == 'unchanged' for item in result))

    def test_reconciliation_rechecks_after_lock_probe(self):
        def refresh(name):
            index = int(name.split('-')[1])
            value = self.ids[index]
            self.repo.heartbeat(value, self.repo.control(value).worker_token, NOW)
        with patch.object(self.repo, 'lock', self.lock_probe(callback=refresh)):
            results = self.repo.reconcile_stale_runs(apply=True, now=NOW)
        self.assertTrue(all(item['action'] == 'unchanged' for item in results))

    def app(self, enabled=True):
        return create_app(dict(TESTING=True, PER_PAGE=1, SECRET_KEY='s'*32,
            COLLECTION_CONTROL_ENABLED=enabled, COLLECTION_CONTROL_TOKEN='t'*32), {'runs': self.service})

    def csrf(self, client):
        client.get('/runs')
        with client.session_transaction() as session:
            return session['collection_csrf']

    def test_get_is_read_only_and_pagination_keeps_filter(self):
        before = self.repo.control(self.ids[0]).last_heartbeat_at
        client = self.app().test_client()
        html = client.get('/runs?status=running').get_data(as_text=True)
        self.assertIn('value="running" selected', html)
        self.assertIn('status=running', html)
        self.assertIn('page=2', html)
        self.assertEqual(self.repo.control(self.ids[0]).last_heartbeat_at, before)
        self.assertIn('Possibly stalled', html)
        self.assertIn('Stop Run', html)
        self.assertNotIn('t'*32, html)
        self.assertEqual(client.get('/runs?status=bogus').status_code, 200)
        self.assertEqual(client.get('/runs?status=completed&page=100').status_code, 302)

    def test_stop_security_and_post_redirect(self):
        client = self.app().test_client()
        path = f'/runs/{self.ids[0]}/stop'
        self.assertEqual(client.get(path).status_code, 405)
        self.assertEqual(client.post(path).status_code, 403)
        csrf = self.csrf(client)
        form = dict(csrf_token=csrf, execution_token='t'*32)
        self.assertEqual(client.post(path, data=dict(form, csrf_token='bad')).status_code, 403)
        self.assertEqual(client.post(path, data=dict(form, execution_token='bad')).status_code, 403)
        self.assertEqual(client.post(path, data=form, environ_overrides={'REMOTE_ADDR':'203.0.113.1'}).status_code, 403)
        response = client.post(path, data=form)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(client.post(path, data=form).status_code, 303)
        self.assertEqual(self.repo.control(self.ids[0]).status, 'running')
        html = client.get(response.location).get_data(as_text=True)
        self.assertIn('disabled>Stop requested', html)
        self.assertEqual(client.post(f'/runs/{uuid4()}/stop', data=form).status_code, 404)
        self.assertEqual(self.app(False).test_client().post(path, data=form).status_code, 403)

    def test_pre_migration_monitor_remains_readable_and_cannot_write_controls(self):
        with self.engine.begin() as connection:
            connection.execute(text('DROP TABLE public.collection_runs'))
            omitted = {'last_heartbeat_at', 'stop_requested_at', 'stop_requested_reason',
                       'finalization_reason', 'worker_token'}
            table = Table('collection_runs', MetaData(), *(
                Column(c.name, JSON() if isinstance(c.type, JSONB) else c.type)
                for c in CollectionRun.__table__.columns if c.name not in omitted), schema='public')
            table.create(connection)
            connection.execute(table.insert().values(id=self.ids[0], run_name='legacy',
                status='running', started_at=NOW, created_at=NOW, configuration={}))
        client = self.app().test_client()
        self.assertEqual(client.get('/runs').status_code, 200)
        html = client.get(f'/runs/{self.ids[0]}').get_data(as_text=True)
        self.assertIn('Worker control unavailable', html)
        self.assertEqual(self.service.request_stop(self.ids[0]), 'unavailable')

    def test_stop_button_absent_from_terminal_detail(self):
        client = self.app().test_client()
        html = client.get(f'/runs/{self.ids[1]}').get_data(as_text=True)
        self.assertNotIn('class="collection-stop', html)
        self.assertNotIn('>Stop Run<', html)
        self.assertEqual(client.post(f'/runs/{self.ids[1]}/stop', data=dict(
            csrf_token=self.csrf(client), execution_token='t'*32)).status_code, 303)
        self.assertEqual(self.repo.control(self.ids[1]).status, 'completed')


class CollectionWorkerTests(unittest.TestCase):
    def services(self):
        objects, articles, runs = FakeObjects(), FakeArticles(), FakeRuns()
        return CollectionPersistence(objects, articles), articles, runs, FakeScans()

    def test_heartbeat_writes_are_bounded_and_stop_detected(self):
        runs = FakeRuns()
        value = runs.resolve('test', {})
        lease = Mock()
        control = WorkerControl(runs, lease)
        with patch('collection.lifecycle.monotonic', side_effect=[0, 1, 2, 29, 30, 31]):
            control.bind(value)
            for _ in range(3):
                control.check(force=True)
            control.check()
            runs.stops[value] = NOW
            with self.assertRaises(CollectionStop):
                control.check(force=True)
        self.assertEqual(len(runs.heartbeats), 2)
        self.assertEqual(control.reason, 'user_requested_stop')

    def test_trial_stop_preserves_saved_work_and_checkpoints(self):
        services = self.services()[:3]
        persistence, articles, runs = services
        publisher = SimpleNamespace(SOURCE='citizen', HOSTS=('citizen.digital',), FEEDS=(), LISTINGS=(),
            accepts=lambda url: True, parse=lambda html, url: dict(source='citizen', url=url,
                canonical_url=url, article_text='Synthetic article', title='Synthetic', author='', language='en',
                published_at='', content_hash=url, parser_version='test'))
        client = Mock(last_request=0.0)
        client.fetch.return_value = Mock(content=b'html', url='https://citizen.digital/news/a',
            headers={'Content-Type':'text/html'}, status_code=200)
        original = persistence.objects.write_json
        def stop_after_save(role, name, state, **kwargs):
            reference = original(role, name, state, **kwargs)
            if state.get('sources', {}).get('citizen', {}).get('saved', 0) >= 1:
                runs.stops[runs.ids['stop-test']] = NOW
            return reference
        with patch.object(trial_scraper, 'SOURCES', {'citizen': publisher}), \
             patch.object(trial_scraper, 'Client', return_value=client), \
             patch.object(trial_scraper, 'candidates', return_value=iter([
                 ('https://citizen.digital/news/a','listing','listing'),
                 ('https://citizen.digital/news/b','listing','listing')])), \
             patch.object(persistence.objects, 'write_json', side_effect=stop_after_save):
            self.assertEqual(trial_scraper.run_trial_extraction(['citizen'], limit=2,
                run_name='stop-test', services=services), 1)
        self.assertEqual(runs.statuses['stop-test'], 'interrupted')
        self.assertEqual(runs.reasons['stop-test'], 'user_requested_stop')
        self.assertEqual(len(articles.items), 1)
        self.assertLessEqual(client.fetch.call_count, 2)
        state = persistence.objects.read_json('runs', 'runs/stop-test/progress.json')
        self.assertEqual(state['status'], 'interrupted')
        self.assertEqual(state['stop_reason'], 'user_requested_stop')
        client.session.close.assert_called_once()

    def config(self):
        return dict(start_month='2026-08', end_month='2026-08', sources=['citizen'],
                    delay=2, max_index_pages=0, max_fetches_per_month=0)

    def test_monthly_zero_work_finalizes_and_releases_clients(self):
        services = self.services()
        client = Mock(last_request=0.0)
        client.fetch.return_value = Mock(json=lambda: [])
        with patch.object(collect_monthly, 'Client', return_value=client):
            result = collect_monthly.run(self.config(), 'empty', services)
        self.assertEqual(result['status'], 'index_scans_finished')
        self.assertEqual(services[2].statuses['empty'], 'index_scans_finished')
        self.assertEqual(len(services[1].items), 0)

    def test_monthly_ctrl_c_and_user_stop_reset_unfinished_scan(self):
        for interruption in (KeyboardInterrupt(), CollectionStop()):
            with self.subTest(kind=type(interruption).__name__):
                services = self.services()
                client = Mock(last_request=0.0)
                client.fetch.side_effect = interruption
                with patch.object(collect_monthly, 'Client', return_value=client):
                    result = collect_monthly.run(self.config(), 'interrupt', services)
                self.assertEqual(result['status'], 'interrupted')
                self.assertEqual(result['scans']['citizen/2026-08']['status'], 'pending')
                self.assertEqual(services[2].statuses['interrupt'], 'interrupted')

    def test_monthly_request_during_final_network_call_is_interrupted(self):
        services = self.services()
        client = Mock(last_request=0.0)
        def response(*args):
            services[2].stops[services[2].ids['late-stop']] = NOW
            return Mock(json=lambda: [])
        client.fetch.side_effect = response
        with patch.object(collect_monthly, 'Client', return_value=client):
            result = collect_monthly.run(self.config(), 'late-stop', services)
        self.assertEqual(result['status'], 'interrupted')
        self.assertEqual(services[2].reasons['late-stop'], 'user_requested_stop')
        self.assertEqual(result['stop_reason'], 'user_requested_stop')

    def test_trial_ctrl_c_is_interrupted_and_unexpected_error_is_failed(self):
        for exception, status in ((KeyboardInterrupt(), 'interrupted'), (RuntimeError('unexpected'), 'failed')):
            with self.subTest(status=status):
                services = self.services()[:3]
                with patch.object(trial_scraper, 'Client', side_effect=exception):
                    if status == 'interrupted':
                        self.assertEqual(trial_scraper.run_trial_extraction(['citizen'],
                            run_name='trial-exit', services=services), 0)
                    else:
                        with self.assertRaises(RuntimeError):
                            trial_scraper.run_trial_extraction(['citizen'], run_name='trial-exit', services=services)
                self.assertEqual(services[2].statuses['trial-exit'], status)
                state = services[0].objects.read_json('runs', 'runs/trial-exit/progress.json')
                self.assertEqual(state['status'], status)

    def test_sigterm_requests_safe_checkpoint_and_restores_handler(self):
        services = self.services()
        client = Mock(last_request=0.0)
        original_handler = signal.getsignal(signal.SIGTERM)
        def response(*args):
            handler = signal.getsignal(signal.SIGTERM)
            self.assertTrue(callable(handler))
            handler(signal.SIGTERM, None)
            return Mock(json=lambda: [])
        client.fetch.side_effect = response
        with patch.object(collect_monthly, 'Client', return_value=client):
            result = collect_monthly.run(self.config(), 'shutdown', services)
        self.assertEqual(result['status'], 'interrupted')
        self.assertEqual(result['stop_reason'], 'process_shutdown')
        self.assertEqual(services[2].reasons['shutdown'], 'process_shutdown')
        self.assertEqual(signal.getsignal(signal.SIGTERM), original_handler)

    def test_ctrl_c_during_pending_index_recovery_checkpoints_loaded_state(self):
        services = self.services()
        state = collect_monthly.initial_state(self.config(), ['2026-08'])
        state['pending_index'] = [{'synthetic': 'already durable'}]
        services[0].objects.write_json('runs', 'runs/recovery/progress.json', state)
        with patch.object(services[0], 'retry_index', side_effect=KeyboardInterrupt()):
            with self.assertRaises(KeyboardInterrupt):
                collect_monthly.run(self.config(), 'recovery', services)
        persisted = services[0].objects.read_json('runs', 'runs/recovery/progress.json')
        self.assertEqual(persisted['status'], 'interrupted')
        self.assertEqual(persisted['pending_index'], state['pending_index'])
        self.assertEqual(services[2].statuses['recovery'], 'interrupted')

    def test_setup_failure_does_not_leave_running_row(self):
        services = self.services()
        with patch.object(services[0].objects, 'read_json', side_effect=RuntimeError('storage unavailable')):
            with self.assertRaises(RuntimeError):
                collect_monthly.run(self.config(), 'setup', services)
        self.assertEqual(services[2].statuses['setup'], 'failed')

    def test_final_gcs_checkpoint_failure_still_finalizes_database(self):
        services = self.services()
        client = Mock(last_request=0.0)
        client.fetch.return_value = Mock(json=lambda: [])
        original = collect_monthly.report
        def report(*args):
            if args[2]['status'] != 'running':
                raise RuntimeError('checkpoint unavailable')
            return original(*args)
        with patch.object(collect_monthly, 'Client', return_value=client), \
             patch.object(collect_monthly, 'report', side_effect=report), self.assertRaises(RuntimeError):
            collect_monthly.run(self.config(), 'checkpoint', services)
        self.assertEqual(services[2].statuses['checkpoint'], 'failed')
        self.assertEqual(client.session.close.call_count, 2)

    def test_lock_acquisition_failure_creates_no_run(self):
        services = self.services()
        services[2].lock = Mock(side_effect=CollectionLockBusy())
        with self.assertRaises(CollectionLockBusy):
            collect_monthly.run(self.config(), 'busy', services)
        self.assertEqual(services[2].ids, {})

    def test_lost_lease_cannot_finalize_successor(self):
        services = self.services()
        lease = Mock()
        lease.check.side_effect = [None, CollectionLockLost(), CollectionLockLost()]
        @contextmanager
        def lock(name):
            yield lease
        @managed_collection
        def work(run_name, services):
            bind_run(services[2].resolve(run_name, {}))
            lease.check()
            terminal_status('completed')
        with patch.object(services[2], 'lock', lock), self.assertRaises(CollectionLockLost):
            work('lost', services)
        self.assertEqual(services[2].statuses['lost'], 'running')

    def test_lock_release_error_does_not_undo_durable_completion(self):
        services = self.services()
        connection = MagicMock()
        connection.execute.side_effect = [Mock(one=lambda: (True, 123)),
            Mock(one=lambda: (123, True)), Mock(one=lambda: (123, True)),
            OperationalError('unlock', {}, Exception('connection lost'))]
        engine = MagicMock()
        engine.url = SimpleNamespace(host='direct.example', port=5432)
        engine.connect.return_value.execution_options.return_value.__enter__.return_value = connection
        repository = CollectionRunRepository(SimpleNamespace(kw={'bind': engine}))
        @managed_collection
        def work(run_name, services):
            bind_run(services[2].resolve(run_name, {}))
            terminal_status('completed')
            return 'success'
        with patch.object(services[2], 'lock', repository.lock):
            self.assertEqual(work('release', services), 'success')
        self.assertEqual(services[2].statuses['release'], 'completed')
        connection.invalidate.assert_called_once()
        engine.connect.return_value.execution_options.assert_called_once_with(isolation_level='AUTOCOMMIT')

    def test_changed_backend_refuses_ownership_and_invalidates(self):
        from database.repositories.collection_runs import CollectionLease
        connection = Mock()
        connection.execute.return_value.one.return_value = (456, True)
        lease = CollectionLease(connection, 'run-key', 123)
        with self.assertRaises(CollectionLockLost):
            lease.check()
        self.assertTrue(lease.lost)
        connection.invalidate.assert_called_once()

    def test_transaction_pooler_rejected_before_lock_or_run_write(self):
        engine = Mock(url=SimpleNamespace(host='pooler.supabase.com', port=6543))
        repository = CollectionRunRepository(SimpleNamespace(kw={'bind': engine}))
        with self.assertRaisesRegex(RuntimeError, 'session pooling'):
            with repository.lock('unsupported'):
                self.fail('Acquired unsupported lock')
        engine.connect.assert_not_called()

    def test_long_fresh_job_is_running_and_legacy_is_only_possibly_stalled(self):
        run = SimpleNamespace(status='running', started_at=NOW-timedelta(days=3), finished_at=None,
                              last_heartbeat_at=NOW, stop_requested_at=None)
        self.assertEqual(run_liveness(run, now=NOW)['label'], 'Running')
        run.last_heartbeat_at = None
        self.assertEqual(run_liveness(run, now=NOW)['label'], 'Possibly stalled')


if __name__ == '__main__':
    unittest.main()
