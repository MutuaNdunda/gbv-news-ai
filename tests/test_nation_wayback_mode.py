from unittest import TestCase
from unittest.mock import Mock, patch
from scrapers import nation_wayback
from scripts import trial_scraper
from tests.test_nation_archive import ORIGINAL, HTML
from tests.storage_fakes import FakeObjects, FakeArticles, FakeRuns
from storage.persistence import CollectionPersistence


def cdx_row(url=ORIGINAL):
    return f'africa,nation)/kenya/business/sample 20240616122729 {url} text/html 200 ABCDEFGHIJKLMNOPQRSTUVWXYZ123456 1234'


class NationWaybackModeTests(TestCase):
    def test_publication_window_excludes_missing_and_outside_dates(self):
        objects, articles, runs = FakeObjects(), FakeArticles(), FakeRuns()
        services = CollectionPersistence(objects, articles), articles, runs
        originals = [ORIGINAL.replace('1234567', str(1234567 + index)) for index in range(3)]
        client = Mock(user_agent='SyntheticTestBot')
        responses = [Mock(text='\n'.join(cdx_row(url) for url in originals))]
        for index, url in enumerate(originals):
            html = HTML.replace(ORIGINAL, url)
            if index == 1:
                html = html.replace('2024-06-16T11:09:36Z', '2026-08-31T11:09:36Z')
            elif index == 2:
                html = html.replace('2024-06-16T11:09:36Z', '')
            responses.append(Mock(url='https://web.archive.org/web/20240616122729id_/' + url,
                                  content=html.encode(), headers={'Content-Type': 'text/html'}, status_code=200))
        client.fetch.side_effect = responses
        with patch.object(trial_scraper, 'Client', return_value=client):
            saved = trial_scraper.run_trial_extraction(['nation'], limit=5, run_name='publication-window',
                services=services, wayback=True, max_index_requests=1, publication_start='2026-01-01', publication_end='2026-08-31')
        self.assertEqual(saved, 1)
        import json
        state = json.loads(objects.data[('runs', 'runs/publication-window/progress.json')])
        self.assertEqual(state['sources']['nation']['outside_publication_window'], 1)
        self.assertEqual(state['sources']['nation']['publication_date_missing'], 1)
        self.assertEqual(len(articles.versions), 1)

    def test_actual_library_discovery_paginates_and_deduplicates(self):
        second = ORIGINAL.replace('1234567', '2345678')
        client = Mock(user_agent='SyntheticTestBot')
        client.fetch.side_effect = [Mock(text=cdx_row() + '\n\nnext%21'),
                                    Mock(text=cdx_row() + '\n' + cdx_row(second))]
        found = list(nation_wayback.candidates(client, 2, start='20240601', end='20240630'))
        self.assertEqual(len(found), 2)
        self.assertIn('from=20240601', found[0][1])
        self.assertIn('resumeKey=next%21', found[1][1])
        self.assertEqual(found[0][2], 'waybackpy_cdx')

    def test_resolution_and_missing_archive(self):
        client = Mock(user_agent='SyntheticTestBot')
        client.fetch.return_value = Mock(text=cdx_row())
        found = list(nation_wayback.candidates(client, urls=[ORIGINAL]))
        self.assertEqual(len(found), 1)
        self.assertIn('matchType=exact', found[0][1])
        self.assertIn('limit=500', found[0][1])
        client.fetch.return_value = Mock(text='')
        self.assertEqual(list(nation_wayback.candidates(client, urls=[ORIGINAL])), [])

    def test_failed_index_is_not_successful_empty_coverage(self):
        client = Mock(user_agent='SyntheticTestBot')
        client.fetch.return_value = None
        with self.assertRaisesRegex(RuntimeError, 'coverage incomplete'):
            list(nation_wayback.candidates(client))

    def test_endpoint_and_other_publishers_are_restricted(self):
        self.assertTrue(nation_wayback.accepts_fetch('https://web.archive.org/cdx/search/cdx?url=nation.africa'))
        self.assertFalse(nation_wayback.accepts_fetch('https://web.archive.org/web/20240616122729/https://example.com/a'))
        self.assertFalse(nation_wayback.accepts_fetch('https://example.com/cdx/search/cdx'))

    def test_section_scope_is_recorded_in_actual_query(self):
        client = Mock(user_agent='SyntheticTestBot')
        client.fetch.return_value = Mock(text=cdx_row())
        found = list(nation_wayback.candidates(client, section='news'))
        self.assertIn('url=https%3A%2F%2Fnation.africa%2Fkenya%2Fnews%2F', found[0][1])

    def test_cloud_storage_exact_lineage_and_second_run_duplicate(self):
        objects, articles, runs = FakeObjects(), FakeArticles(), FakeRuns()
        services = CollectionPersistence(objects, articles), articles, runs
        replay = 'https://web.archive.org/web/20240616122729id_/' + ORIGINAL
        client = Mock(user_agent='SyntheticTestBot')
        client.fetch.side_effect = [Mock(text=cdx_row()),
                                    Mock(url=replay, content=HTML.encode(),
                                         headers={'Content-Type': 'text/html'}, status_code=200)]
        with patch.object(trial_scraper, 'Client', return_value=client):
            saved = trial_scraper.run_trial_extraction(['nation'], limit=1, run_name='wayback-test',
                                                       services=services, wayback=True, max_index_requests=1)
        self.assertEqual(saved, 1)
        processed = [value for (role, _), value in objects.data.items() if role == 'processed'][0]
        import json
        article = json.loads(processed)
        self.assertEqual(article['url'], ORIGINAL)
        self.assertEqual(article['archive_url'], replay)
        self.assertEqual(article['archive_capture_timestamp'], '20240616122729')
        self.assertEqual(article['published_at'], '2024-06-16T11:09:36Z')
        self.assertIn('final paragraph', article['article_text'])
        self.assertIn('cdx/search/cdx', article['discovery_url'])
        client.fetch.side_effect = [Mock(text=cdx_row())]
        with patch.object(trial_scraper, 'Client', return_value=client):
            saved = trial_scraper.run_trial_extraction(['nation'], limit=1, run_name='wayback-test',
                                                       services=services, wayback=True, max_index_requests=1)
        self.assertEqual(saved, 0)
        self.assertEqual(len(articles.versions), 1)
