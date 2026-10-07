import io
import json
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from contextlib import redirect_stdout

from scripts import trial_scraper
from scrapers import nation, citizen, standard, star, tuko, kenyans, taifaleo
from scrapers.wayback_discovery import ArchiveSource, Discovery, term_pattern
from storage.persistence import CollectionPersistence
from tests.storage_fakes import FakeArticles, FakeObjects, FakeRuns

URLS = {
    'nation': 'https://nation.africa/kenya/news/sample-rape-report-1234567',
    'standard': 'https://www.standardmedia.co.ke/article/123456/sample-rape-report',
    'star': 'https://www.the-star.co.ke/news/2026-03-01-sample-rape-report',
    'citizen': 'https://citizen.digital/news/sample-rape-report-n123456',
    'tuko': 'https://www.tuko.co.ke/kenya/123456-sample-rape-report/',
    'kenyans': 'https://www.kenyans.co.ke/news/123456-sample-rape-report',
    'taifaleo': 'https://taifaleo.nation.co.ke/sample-rape-report/',
}


def row(url, timestamp='20260301000000'):
    return f'org,synthetic)/sample {timestamp} {url} text/html 200 ABCDEFGHIJKLMNOPQRSTUVWXYZ123456 1234'


class SharedDiscoveryTests(unittest.TestCase):
    def discovery(self, text, publisher=nation, **kwargs):
        client = Mock(user_agent='SyntheticTestBot')
        client.fetch.return_value = Mock(text=text)
        return Discovery(ArchiveSource(publisher), client, max_requests=1, **kwargs)

    def test_or_case_escaping_and_encoded_spaces(self):
        pattern = term_pattern(['sexual assault', 'FGM', 'a.b', 'C++', 'wife (killed)'])
        for text in ['https://x/SEXUAL-ASSAULT', 'https://x/sexual%20assault',
                     'https://x/sexual+assault', 'https://x/fgm', 'https://x/a.b',
                     'https://x/C++', 'https://x/wife-(killed)']:
            self.assertRegex(text, pattern)
        self.assertIsNone(re.fullmatch(pattern, 'https://x/axb'))
        self.assertIsNone(term_pattern([]))
        with self.assertRaises(ValueError):
            term_pattern(['  '])

    def test_terms_are_applied_to_original_cdx_field(self):
        d = self.discovery(row(URLS['nation']), terms=['rape', 'FGM'])
        self.assertEqual(len(list(d.candidates())), 1)
        from urllib.parse import parse_qs, urlsplit
        params = parse_qs(urlsplit(d.client.fetch.call_args.args[0]).query)
        self.assertIn('original:' + term_pattern(['rape', 'FGM']), params['filter'])
        self.assertNotIn('collapse', params)

    def test_all_registered_publishers_route_and_normalize(self):
        self.assertEqual(set(URLS), set(trial_scraper.SOURCES))
        for name, publisher in trial_scraper.SOURCES.items():
            with self.subTest(source=name):
                adapter = ArchiveSource(publisher)
                d = self.discovery(row(URLS[name]), publisher)
                found = list(d.candidates())
                self.assertEqual(len(found), 1)
                self.assertTrue(publisher.accepts(found[0][0]))
                self.assertEqual(adapter.identity(URLS[name]), adapter.identity(found[0][0]))
                self.assertFalse(adapter.accepts_fetch('https://web.archive.org/web/20260301000000/https://example.com/a'))
                self.assertFalse(publisher.is_article('https://' + publisher.PUBLISHER_HOSTS[0] + '/'))

    def test_selection_deduplicates_aliases_and_is_timestamp_based(self):
        url = URLS['nation']
        alias = url.replace('https://nation.africa', 'http://www.nation.africa') + '?utm_source=synthetic'
        text = '\n'.join([row(url, '20250101000000'), row(alias, '20260101000000'), row(url, '20240101000000')])
        for selection, expected in [('newest', '20260101000000'), ('oldest', '20250101000000')]:
            d = self.discovery(text, selection=selection, start='20250101', end='20261231')
            found = list(d.candidates())
            self.assertEqual(len(found), 1)
            self.assertIn(expected, found[0][0])
            self.assertEqual(d.stats['capture_duplicates'], 1)

    def test_record_request_and_page_bounds(self):
        url = URLS['nation']
        d = self.discovery(row(url) + '\n' + row(url) + '\n\nkey', max_records=2, max_pages=3)
        self.assertEqual(len(list(d.candidates())), 1)
        self.assertIn('max_records', d.stats['bounds_reached'])
        self.assertEqual(d.stats['index_requests'], 1)
        d = self.discovery(row(url) + '\n\nkey', max_pages=1)
        list(d.candidates())
        self.assertIn('max_pages', d.stats['bounds_reached'])
        self.assertFalse(d.stats['discovery_complete'])

    def test_supplied_urls_resolve_and_direct_replays_respect_dates(self):
        url = URLS['nation']
        d = self.discovery(row(url), urls=[url, url])
        self.assertEqual(len(list(d.candidates())), 1)
        self.assertIn('matchType=exact', d.client.fetch.call_args.args[0])
        replay = 'https://web.archive.org/web/20260301000000id_/' + url
        d = self.discovery('', urls=[replay], start='20260301', end='20260331')
        self.assertEqual(len(list(d.candidates())), 1)
        d.client.fetch.assert_not_called()
        d = self.discovery('', urls=[replay], end='20250101')
        self.assertEqual(list(d.candidates()), [])

    def test_invalid_login_foreign_and_category_routes_excluded(self):
        text = '\n'.join(row(url) for url in ['https://nation.africa/kenya/',
            'https://nation.africa/kenya/news/', 'https://nation.africa/kenya/account/signin?redirect_to=' + URLS['nation'],
            'https://example.com/kenya/news/sample-1234567'])
        publisher = SimpleNamespace(**vars(nation))
        publisher.ARCHIVE_PREFIXES = nation.ARCHIVE_PREFIXES[:1]
        d = self.discovery(text, publisher)
        self.assertEqual(list(d.candidates()), [])
        self.assertEqual(d.stats['invalid_routes'], 4)
        self.assertEqual(d.stats['discovery_stop_reason'], 'no_valid_candidates')


class SharedRunnerTests(unittest.TestCase):
    def services(self):
        objects, articles, runs = FakeObjects(), FakeArticles(), FakeRuns()
        return (CollectionPersistence(objects, articles), articles, runs)

    def test_continue_past_duplicates_fetch_and_parser_failures_until_save(self):
        from tests.test_nation_archive import HTML, ORIGINAL
        services = self.services()
        urls = [ORIGINAL.replace('1234567', str(1234567 + index)) for index in range(4)]
        services[1].items.append(({'source': 'nation', 'canonical_url': urls[0], 'content_hash': 'known'}, None))
        replays = ['https://web.archive.org/web/20260301000000id_/' + url for url in urls]
        client = Mock(user_agent='SyntheticTestBot')
        client.fetch.side_effect = [None,
            Mock(url=replays[2], content=b'<h1>No body</h1>', headers={'Content-Type':'text/html'}, status_code=200),
            Mock(url=replays[3], content=HTML.replace(ORIGINAL, urls[3]).encode(), headers={'Content-Type':'text/html'}, status_code=200)]
        with patch.object(trial_scraper, 'Client', return_value=client):
            self.assertEqual(trial_scraper.run_trial_extraction(['nation'], limit=1, services=services,
                method='wayback', wayback_urls=replays, run_name='continue', max_attempts=4), 1)
        source = services[0].objects.read_json('runs', 'runs/continue/progress.json')['sources']['nation']
        self.assertEqual(source['duplicates'], 1)
        self.assertEqual(source['fetch_failed'], 1)
        self.assertEqual(source['parse_failed'], 1)
        self.assertEqual(source['extraction_successes'], 1)
        self.assertEqual(source['stop_reason'], 'article_limit')

    def test_extraction_attempt_bound_is_explicit(self):
        services = self.services()
        replays = ['https://web.archive.org/web/20260301000000id_/' + URLS['nation'].replace('1234567', str(1234567+i)) for i in range(3)]
        client = Mock(user_agent='SyntheticTestBot')
        client.fetch.return_value = None
        with patch.object(trial_scraper, 'Client', return_value=client):
            self.assertEqual(trial_scraper.run_trial_extraction(['nation'], limit=2, services=services,
                method='wayback', wayback_urls=replays, run_name='attempt-bound', max_attempts=1), 0)
        source = services[0].objects.read_json('runs', 'runs/attempt-bound/progress.json')['sources']['nation']
        self.assertEqual(source['attempted'], 1)
        self.assertEqual(source['stop_reason'], 'max_attempts')

    def test_raw_storage_failure_is_counted_and_collection_continues(self):
        from tests.test_nation_archive import HTML, ORIGINAL
        services = self.services()
        replay = 'https://web.archive.org/web/20260301000000id_/' + ORIGINAL
        client = Mock(user_agent='SyntheticTestBot')
        client.fetch.return_value = Mock(url=replay, content=HTML.encode(), headers={'Content-Type':'text/html'}, status_code=200)
        with patch.object(trial_scraper, 'Client', return_value=client), \
             patch.object(services[0], 'store_raw', side_effect=RuntimeError('synthetic storage failure')), \
             self.assertLogs('scripts.trial_scraper', level='ERROR'):
            self.assertEqual(trial_scraper.run_trial_extraction(['nation'], services=services, method='wayback',
                wayback_urls=[replay], run_name='raw-fail'), 0)
        state = services[0].objects.read_json('runs', 'runs/raw-fail/progress.json')
        self.assertEqual(state['sources']['nation']['storage_failed'], 1)
        self.assertEqual(state['status'], 'finished_with_gaps')

    def test_normalized_storage_failure_retains_raw_and_reports_gap(self):
        from tests.test_nation_archive import HTML, ORIGINAL
        services = self.services()
        replay = 'https://web.archive.org/web/20260301000000id_/' + ORIGINAL
        client = Mock(user_agent='SyntheticTestBot')
        client.fetch.return_value = Mock(url=replay, content=HTML.encode(), headers={'Content-Type':'text/html'}, status_code=200)
        with patch.object(trial_scraper, 'Client', return_value=client), \
             patch.object(services[0], 'persist_article', side_effect=RuntimeError('synthetic normalized write failure')), \
             self.assertLogs('scripts.trial_scraper', level='ERROR'):
            self.assertEqual(trial_scraper.run_trial_extraction(['nation'], services=services, method='wayback',
                wayback_urls=[replay], run_name='normalized-fail'), 0)
        state = services[0].objects.read_json('runs', 'runs/normalized-fail/progress.json')
        self.assertEqual(state['sources']['nation']['raw_stored'], 1)
        self.assertEqual(state['sources']['nation']['storage_failed'], 1)
        self.assertEqual(state['status'], 'finished_with_gaps')

    def test_failure_for_one_publisher_continues_and_records_gap(self):
        services = self.services()
        clients = [Mock(user_agent='SyntheticTestBot'), Mock(user_agent='SyntheticTestBot')]
        clients[0].fetch.return_value = None
        clients[1].fetch.return_value = Mock(text='')
        with patch.object(trial_scraper, 'Client', side_effect=clients):
            total = trial_scraper.run_trial_extraction(['nation', 'citizen'], services=services,
                run_name='partial', method='wayback', max_index_requests=1)
        self.assertEqual(total, 0)
        state = services[0].objects.read_json('runs', 'runs/partial/progress.json')
        self.assertEqual(state['status'], 'finished_with_gaps')
        self.assertEqual(state['sources']['nation']['discovery']['index_failures'], 1)
        self.assertEqual(state['sources']['citizen']['stop_reason'], 'max_index_requests')

    def test_offline_dry_run_never_initializes_cloud_or_http(self):
        output = io.StringIO()
        with patch.object(trial_scraper, 'build_services', side_effect=AssertionError('cloud')), \
                patch.object(trial_scraper, 'Client', side_effect=AssertionError('network')), \
                patch.object(trial_scraper, 'load_environment', side_effect=AssertionError('env')), redirect_stdout(output):
            trial_scraper.main(['--sources', 'nation', 'tuko', '--term', 'rape', '--dry-run'])
        plan = json.loads(output.getvalue())
        self.assertEqual(plan['method'], 'wayback')
        self.assertEqual(plan['sources'], ['nation', 'tuko'])
        self.assertEqual(plan['terms'], ['rape'])

    def test_missing_archive_adapter_is_explicit_without_fallback(self):
        services = self.services()
        unsupported = SimpleNamespace(**vars(nation))
        del unsupported.ARCHIVE_PREFIXES
        client = Mock(user_agent='SyntheticTestBot')
        with patch.object(trial_scraper, 'SOURCES', {'nation':unsupported}), \
             patch.object(trial_scraper, 'Client', return_value=client), self.assertLogs('scripts.trial_scraper', level='WARNING'):
            self.assertEqual(trial_scraper.run_trial_extraction(['nation'], services=services,
                method='wayback', run_name='unsupported'), 0)
        client.fetch.assert_not_called()
        state = services[0].objects.read_json('runs','runs/unsupported/progress.json')
        self.assertEqual(state['sources']['nation']['stop_reason'],'unsupported_archive_adapter')
        self.assertEqual(state['status'],'finished_with_gaps')

    def test_date_and_limit_validation_precedes_io(self):
        for args in [['--from-date', '2026-02-30'], ['--from-date', '2026-05-01', '--to-date', '2025-01-01'],
                     ['--max-records', '0'], ['--max-index-requests', '0'], ['--term', ' ']]:
            with self.subTest(args=args), redirect_stdout(io.StringIO()), patch('sys.stderr', io.StringIO()):
                with self.assertRaises(SystemExit):
                    trial_scraper.parse_args(args + ['--dry-run'])

    def test_source_specific_live_extractors_have_no_archive_fields(self):
        for name, publisher in trial_scraper.SOURCES.items():
            fixture = Path(__file__).parent / f'fixtures/{name}_archive_article.html'
            html = fixture.read_bytes()
            soup = __import__('bs4').BeautifulSoup(html, 'lxml')
            canonical = soup.select_one('link[rel="canonical"]')['href']
            parts = publisher.archive_parts(canonical)
            url = parts[1] if parts else canonical
            with self.subTest(source=name):
                result = publisher.parse_live(html, url)
                self.assertIsNotNone(result)
                self.assertNotIn('archive_url', result)
                self.assertNotIn('archive_capture_timestamp', result)

    def test_seven_extraction_adapters_use_same_raw_first_cloud_workflow(self):
        from bs4 import BeautifulSoup
        services = self.services()
        replays, clients = [], []
        for name, publisher in trial_scraper.SOURCES.items():
            html = (Path(__file__).parent / f'fixtures/{name}_archive_article.html').read_bytes()
            canonical = BeautifulSoup(html, 'lxml').select_one('link[rel="canonical"]')['href']
            parts = publisher.archive_parts(canonical)
            url = parts[1] if parts else canonical
            replay = 'https://web.archive.org/web/20260301000000id_/' + url
            replays.append(replay)
            client = Mock(user_agent='SyntheticTestBot')
            client.fetch.return_value = Mock(url=replay, content=html, headers={'Content-Type':'text/html'}, status_code=200)
            clients.append(client)
        with patch.object(trial_scraper, 'Client', side_effect=clients):
            total = trial_scraper.run_trial_extraction(list(trial_scraper.SOURCES), limit=1,
                services=services, method='wayback', wayback_urls=replays, run_name='seven-adapters')
        self.assertEqual(total, 7)
        self.assertEqual({item['source'] for item, _ in services[1].items}, set(trial_scraper.SOURCES))
        for item, _ in services[1].items:
            self.assertTrue(item['article_text'])
            self.assertEqual(item['archive_capture_timestamp'], '20260301000000')
            self.assertIn('raw_object_uri', item)

    def test_indexing_failure_keeps_pending_recovery_and_other_sources_run(self):
        from bs4 import BeautifulSoup
        services = self.services()
        services[1].fail_persist = True
        replays, clients = [], []
        for name in ['nation', 'citizen']:
            publisher = trial_scraper.SOURCES[name]
            html = (Path(__file__).parent / f'fixtures/{name}_archive_article.html').read_bytes()
            canonical = BeautifulSoup(html, 'lxml').select_one('link[rel="canonical"]')['href']
            parts = publisher.archive_parts(canonical)
            original = parts[1] if parts else canonical
            replay = 'https://web.archive.org/web/20260301000000id_/' + original
            replays.append(replay)
            client = Mock(user_agent='SyntheticTestBot')
            client.fetch.return_value = Mock(url=replay, content=html, headers={'Content-Type':'text/html'}, status_code=200)
            clients.append(client)
        with patch.object(trial_scraper, 'Client', side_effect=clients), self.assertLogs('scripts.trial_scraper', level='WARNING'):
            self.assertEqual(trial_scraper.run_trial_extraction(['nation','citizen'], services=services,
                method='wayback', wayback_urls=replays, run_name='index-fail'), 0)
        state = services[0].objects.read_json('runs', 'runs/index-fail/progress.json')
        self.assertEqual(len(state['pending_index']), 2)
        self.assertEqual(state['sources']['citizen']['stop_reason'], 'storage_index_failed')
        self.assertEqual(state['status'], 'finished_with_gaps')

    def test_live_collection_stays_on_publishers_and_records_no_replay(self):
        from tests.test_nation_archive import HTML, ORIGINAL
        services = self.services()
        client = Mock(user_agent='SyntheticTestBot')
        client.fetch.return_value = Mock(url=ORIGINAL, content=HTML.encode(), headers={'Content-Type':'text/html'}, status_code=200)
        with patch.object(trial_scraper, 'Client', return_value=client) as factory:
            self.assertEqual(trial_scraper.run_trial_extraction(['nation'], limit=1, services=services,
                method='live', wayback_urls=[ORIGINAL], run_name='live-test'), 1)
        self.assertEqual(factory.call_args.args[0], nation.PUBLISHER_HOSTS)
        self.assertNotIn('archive_url', services[1].items[0][0])
