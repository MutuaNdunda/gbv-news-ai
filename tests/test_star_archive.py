"""Offline regressions based on the inspected Star archive structure."""
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from scrapers import star
from scrapers.common import Client
from scripts.trial_scraper import candidates

ORIGINAL = 'https://www.the-star.co.ke/news/2025-12-27-sample-news'
ARCHIVE = 'https://web.archive.org/web/20251227064552/' + ORIGINAL
HTML = (Path(__file__).parent / 'fixtures/star_archive_article.html').read_text()


class StarArchiveTests(unittest.TestCase):
    def test_article_metadata_body_and_dates(self):
        article = star.parse(HTML, ARCHIVE)
        self.assertEqual(article['canonical_url'], ORIGINAL)
        self.assertEqual(article['title'], 'Sample Star news')
        self.assertEqual(article['published_at'], '2025-12-27T04:55')
        self.assertEqual(article['publication_timezone'], 'unknown')
        self.assertEqual(article['archive_capture_timestamp'], '20251227064552')
        self.assertEqual(article['source'], 'star')
        self.assertIn('final paragraph', article['article_text'])
        self.assertNotIn('Footer', article['article_text'])
        self.assertNotIn('toolbar', article['article_text'])

    def test_discovery_rewrites_live_links_and_excludes_navigation(self):
        html = f'<a href="{ORIGINAL}">First</a><a href="{ARCHIVE}">Duplicate</a><a href="/business/kenya/2025-12-26-economy">Business</a><a href="/news">Section</a><a href="https://example.com/news/2025-12-27-story">External</a>'
        links = star.discover(html, star.LISTINGS[0])
        self.assertEqual(len(links), 2)
        self.assertTrue(all(star.accepts(link) for link in links))
        client = Mock()
        client.fetch.return_value = Mock(content=html.encode(), url=star.LISTINGS[0])
        self.assertEqual(list(candidates(star, client))[0][2], 'archive_listing')

    def test_paywall_premium_and_empty_body(self):
        self.assertIsNone(star.parse(HTML.replace('<h1>', '<span class="premium">Premium</span><h1>'), ARCHIVE))
        self.assertIsNone(star.parse(HTML.replace('<footer>', '<aside id="paywall">Subscribe</aside><footer>'), ARCHIVE))
        self.assertIsNone(star.parse('<h1>Only a heading</h1>', ARCHIVE))
        self.assertEqual(star.discover(f'<a href="{ARCHIVE}"><span class="premium">Premium</span></a>',star.LISTINGS[0]), [])

    def test_rejects_foreign_canonical_and_live_redirect(self):
        self.assertIsNone(star.parse(HTML.replace(ARCHIVE, 'https://example.com/news/2025-12-27-story'), ARCHIVE))
        self.assertFalse(star.accepts_fetch(ORIGINAL))
        self.assertFalse(star.accepts_fetch('https://web.archive.org/web/20251227064552/https://example.com/news/2025-12-27-story'))
        client = Client(star.HOSTS, delay=0, url_validator=star.accepts_fetch)
        with patch.object(client, 'permitted', return_value=True), patch.object(client, '_request', return_value=Mock(status_code=302, headers={'Location': ORIGINAL})) as request:
            self.assertIsNone(client.fetch(ARCHIVE))
            self.assertEqual(request.call_count, 1)


if __name__ == '__main__':
    unittest.main()
