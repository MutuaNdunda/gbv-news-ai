import unittest
from unittest.mock import Mock, patch
from scripts.collect_urls import extract_urls
from scripts.trial_scraper import raw_identity_url
from scrapers import nation
from tests.test_nation_archive import HTML, ORIGINAL
from scripts import trial_scraper
from storage.persistence import CollectionPersistence
from tests.storage_fakes import FakeArticles, FakeObjects, FakeRuns


class ExplicitUrlTests(unittest.TestCase):
    def test_live_url_uses_cloud_storage_without_discovery(self):
        objects, articles, runs = FakeObjects(), FakeArticles(), FakeRuns()
        client = Mock()
        client.fetch.return_value = Mock(content=HTML.encode(), url=ORIGINAL,
                                        headers={'Content-Type': 'text/html'}, status_code=200)
        with patch.object(trial_scraper, 'Client', return_value=client):
            saved = trial_scraper.run_trial_extraction(
                sources=['nation'], input_urls=[ORIGINAL], limit=1,
                run_name='manual-test', services=(CollectionPersistence(objects, articles), articles, runs))
        self.assertEqual(saved, 1)
        client.fetch.assert_called_once_with(ORIGINAL, stage='ARTICLE_FETCH')
        self.assertEqual(runs.statuses['manual-test'], 'completed')
        self.assertEqual(len(articles.versions), 1)

    def test_markdown_dedup_and_login_rejection(self):
        login = 'https://nation.africa/kenya/account/signin?redirect_to=' + ORIGINAL
        urls, rejected = extract_urls(f'| [{ORIGINAL}]({ORIGINAL}) |\n{login}\nhttps://example.com/article')
        self.assertEqual(urls, [ORIGINAL])
        self.assertEqual(len(rejected), 2)

    def test_dated_replays_and_live_identity(self):
        replay = 'https://web.archive.org/web/20240616122729id_/' + ORIGINAL
        self.assertEqual(extract_urls(replay)[0], [replay])
        self.assertEqual(raw_identity_url(nation, ORIGINAL), ORIGINAL)

    def test_live_parse_has_no_fake_archive_provenance(self):
        article = nation.parse_live(HTML, ORIGINAL)
        self.assertIsNotNone(article)
        self.assertNotIn('archive_url', article)
        self.assertNotIn('archive_capture_timestamp', article)
        self.assertEqual(article['parser_version'], 'nation-live-1.0')
        self.assertIsNone(nation.parse_live(HTML.replace('id="paywall" class="hidden"', 'id="paywall"'), ORIGINAL))
