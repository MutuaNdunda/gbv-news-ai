"""Synthetic fixtures use the structure inspected in the supplied Wayback snapshot."""
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from scrapers import nation
from scrapers.common import Client
from scripts.trial_scraper import candidates

ORIGINAL = 'https://nation.africa/kenya/business/sample-news-update-1234567'
ARCHIVE = 'https://web.archive.org/web/20240616122729/' + ORIGINAL
HTML = (Path(__file__).parent / 'fixtures/nation_archive_article.html').read_text()


class NationArchiveTests(unittest.TestCase):
    def test_original_url_capture_and_publication_dates_remain_distinct(self):
        article = nation.parse(HTML, ARCHIVE)
        self.assertEqual(article['url'], ORIGINAL)
        self.assertEqual(article['canonical_url'], ORIGINAL)
        self.assertEqual(article['archive_url'], ARCHIVE)
        self.assertEqual(article['archive_capture_timestamp'], '20240616122729')
        self.assertEqual(article['published_at'], '2024-06-16T11:09:36Z')
        self.assertEqual(article['title'], 'Sample news update')
        self.assertEqual(article['publisher_name'], 'Daily Nation')
        self.assertEqual(article['content_scope'], 'news_reporting')
        self.assertNotIn('toolbar', article['article_text'])
        self.assertNotIn('navigation', article['article_text'])
        self.assertIn('final paragraph', article['article_text'])
        self.assertNotIn('Unrelated story', article['article_text'])

    def test_links_stay_archived_and_deduplicated(self):
        html = f'''<a href="{ARCHIVE}">Article</a>
        <a href="{ORIGINAL}">Duplicate</a>
        <a href="/kenya/news/second-update-2345678">Relative original link</a>
        <a href="/web/20240616122729/https://nation.africa/kenya/news/third-update-3456789">Relative replay</a>
        <a href="https://nation.africa/kenya/news/">Pagination</a>
        <a href="https://example.com/news/other/">External</a>'''
        links = nation.discover(html, nation.LISTINGS[0])
        self.assertEqual(len(links), 3)
        self.assertTrue(all(nation.accepts(url) for url in links))
        self.assertIn(ARCHIVE, links)

    def test_other_publishers_live_pages_and_toolbar_routes_rejected(self):
        for url in (ORIGINAL, 'https://web.archive.org/web/20240616122729/https://www.nationmedia.com/news/company-story/',
                    'https://web.archive.org/web/20240616122729/https://example.com/news/story/',
                    'https://web.archive.org/web/20240616122729*/' + ORIGINAL):
            with self.subTest(url=url):
                self.assertFalse(nation.accepts_fetch(url))
                self.assertIsNone(nation.parse(HTML, url))
        self.assertTrue(nation.accepts_fetch(nation.LISTINGS[0]))

    def test_invalid_canonical_and_missing_body(self):
        self.assertIsNone(nation.parse(HTML.replace(ARCHIVE, 'https://example.com/news/test/'), ARCHIVE))
        self.assertIsNone(nation.parse('<h1>News</h1>', ARCHIVE))

    def test_premium_and_active_paywall_rejected(self):
        premium = HTML.replace('<h1>', '<svg class="premium"></svg><h1>')
        self.assertIsNone(nation.parse(premium, ARCHIVE))
        self.assertIsNone(nation.parse(HTML.replace('id="paywall" class="hidden"', 'id="paywall"'), ARCHIVE))
        listing = f'<a href="{ARCHIVE}"><svg class="premium"></svg>Premium story</a>'
        self.assertEqual(nation.discover(listing, nation.LISTINGS[0]), [])

    def test_discovery_uses_archive_adapter(self):
        response = Mock(content=f'<a href="{ORIGINAL}">Article</a>'.encode(), url=nation.LISTINGS[0])
        client = Mock()
        client.fetch.return_value = response
        found = list(candidates(nation, client))
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0][2], 'archive_listing')
        self.assertTrue(nation.accepts(found[0][0]))

    def test_redirect_to_other_archived_publisher_is_blocked(self):
        client = Client(nation.HOSTS, delay=0, url_validator=nation.accepts_fetch)
        redirect = Mock(status_code=302, headers={'Location': 'https://web.archive.org/web/20240616122729/https://example.com/news/story/'})
        with patch.object(client, 'permitted', return_value=True), patch.object(client, '_request', return_value=redirect) as request:
            self.assertIsNone(client.fetch(ARCHIVE))
            self.assertEqual(request.call_count, 1)


if __name__ == '__main__':
    unittest.main()
