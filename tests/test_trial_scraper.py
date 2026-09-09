"""Offline regression tests using synthetic content, with no publisher requests."""
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

from scrapers import citizen, nation, standard, star
from scrapers.common import Client, allowed_url, discover, parse_article
from scripts import trial_scraper
from scripts.trial_scraper import raw_identity_url
from storage.persistence import CollectionPersistence, article_identifier
from tests.storage_fakes import FakeArticles, FakeObjects, FakeRuns

FIXTURE = Path(__file__).parent / 'fixtures/trial_article.html'
URL = 'https://citizen.digital/news/county-schools-open-n12345'


def parse_fixture(html, url):
    return parse_article(html, url, 'citizen', citizen.PUBLISHER_HOSTS, ('.article-body',))


class TrialTests(unittest.TestCase):
    def test_metadata_and_null_author(self):
        result = parse_fixture(FIXTURE.read_text(), URL)
        self.assertEqual(result['title'], 'County schools open')
        self.assertEqual(result['author'], '')
        self.assertEqual(result['source'], 'citizen')
        self.assertEqual(result['language'], 'sw')
        self.assertEqual(result['published_at'], '2026-09-08T09:00:00+03:00')
        self.assertEqual(result['canonical_url'], URL)
        self.assertNotIn('Unrelated navigation', result['article_text'])
        self.assertEqual(result['kenya_relevance'], 'needs_review')

    def test_publisher_body_fallbacks_and_unknown_language(self):
        for publisher in (standard,):
            with self.subTest(source=publisher.SOURCE):
                html = '<h1>County water project</h1><div class="article-body"><p>New water infrastructure opened today.</p></div>'
                result = parse_article(html, 'https://standardmedia.co.ke/news/example', publisher.SOURCE, publisher.PUBLISHER_HOSTS, ('.article-body',))
                self.assertEqual(result['article_text'], 'New water infrastructure opened today.')
                self.assertEqual(result['language'], '')
                self.assertEqual(result['source'], publisher.SOURCE)

    def test_rejects_paywall_and_foreign_canonical(self):
        html = FIXTURE.read_text()
        self.assertIsNone(parse_fixture(html.replace('"author":null', '"isAccessibleForFree":false'), URL))
        self.assertIsNone(parse_fixture(html.replace('/news/county-schools-open-n12345', 'https://example.com/article'), URL))
        self.assertIsNone(parse_fixture('<h1>Listing only</h1>', URL))

    def test_discovery_excludes_external_links_and_section_pages(self):
        html = f'<a href="{URL}">School</a><a href="{URL}#top">Repeat</a><a href="https://evil.example/news/story-n123">Other</a><a href="/news">Section</a>'
        self.assertEqual(discover(html, URL, citizen.is_article), [URL])
        self.assertFalse(allowed_url('https://citizen.digital.evil.example/a', citizen.PUBLISHER_HOSTS))
        self.assertFalse(allowed_url('https://user:pass@citizen.digital/a', citizen.PUBLISHER_HOSTS))
        self.assertFalse(star.accepts('https://www.the-star.co.ke/news/world/2026-09-08-example'))

    def test_article_identity_and_archive_raw_identity(self):
        self.assertEqual(len(article_identifier('citizen', URL)), 64)
        replay = 'https://web.archive.org/web/20260908000000/' + URL
        self.assertEqual(raw_identity_url(citizen, replay), URL)

    def test_trial_run_uses_gcs_artifacts_and_supabase_lineage(self):
        objects, articles, runs = FakeObjects(), FakeArticles(), FakeRuns()
        services = (CollectionPersistence(objects, articles), articles, runs)

        def parse(html, url):
            self.assertTrue(any(role == "raw" for role, _ in objects.writes))
            item = parse_fixture(FIXTURE.read_text(), URL)
            item["parser_version"] = "citizen-test"
            return item

        publisher = SimpleNamespace(
            SOURCE="citizen", HOSTS=("citizen.digital",), FEEDS=(), LISTINGS=(URL,),
            accepts=lambda url: True, accepts_fetch=lambda url: True,
            parse=parse,
        )
        listing = Mock(content=f'<a href="{URL}">article</a>'.encode(), url=URL)
        article_response = Mock(content=FIXTURE.read_bytes(), url=URL,
                                headers={"Content-Type": "text/html"}, status_code=200)
        client = Mock()
        client.fetch.side_effect = [listing, article_response]
        with patch.object(trial_scraper, "SOURCES", {"citizen": publisher}), \
                patch.object(trial_scraper, "Client", return_value=client):
            saved = trial_scraper.run_trial_extraction(
                ["citizen"], limit=1, run_name="trial-test", services=services
            )
        self.assertEqual(saved, 1)
        self.assertEqual(len(articles.versions), 1)
        self.assertIn(("runs", "runs/trial-test/progress.json"), objects.data)
        self.assertIn(("runs", "runs/trial-test/trial_counts.csv"), objects.data)
        self.assertEqual(runs.statuses["trial-test"], "completed")

    def test_robots_denial_blocks_article(self):
        client = Client(citizen.PUBLISHER_HOSTS, delay=0)
        response = Mock(status_code=200, text='User-agent: *\nDisallow: /', headers={'Content-Type': 'text/plain'})
        with patch.object(client, '_request', return_value=response) as request:
            self.assertIsNone(client.fetch(URL))
            self.assertEqual(request.call_count, 1)

    def test_redirect_does_not_fetch_external_host(self):
        client = Client(citizen.PUBLISHER_HOSTS, delay=0)
        response = Mock(status_code=302, headers={'Location': 'https://external.example/story'})
        with patch.object(client, 'permitted', return_value=True), patch.object(client, '_request', return_value=response) as request:
            self.assertIsNone(client.fetch(URL))
            self.assertEqual(request.call_count, 1)

    def test_unknown_robots_policy_blocks_article(self):
        client = Client(citizen.PUBLISHER_HOSTS, delay=0)
        with patch.object(client, '_request', return_value=Mock(status_code=403)) as request:
            self.assertIsNone(client.fetch(URL))
            self.assertEqual(request.call_count, 1)


if __name__ == '__main__':
    unittest.main()
