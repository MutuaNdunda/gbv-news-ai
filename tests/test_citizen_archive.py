"""Regression cases for Citizen's inspected archived HTML."""
from pathlib import Path
import unittest
from scrapers import citizen

URL = 'https://web.archive.org/web/20260309182207/https://citizen.digital/article/sample-news-n12345'
HTML = (Path(__file__).parent / 'fixtures/citizen_archive_article.html').read_text()


class CitizenArchiveTests(unittest.TestCase):
    def test_escaped_metadata_nested_author_and_body(self):
        result = citizen.parse(HTML, URL)
        self.assertEqual(result['author'], 'Test Reporter')
        self.assertEqual(result['title'], 'Sample Citizen article')
        self.assertEqual(result['published_at'], '2026-03-03T21:15:05')
        self.assertEqual(result['publication_timezone'], 'unknown')
        self.assertEqual(result['archive_capture_timestamp'], '20260309182207')
        self.assertEqual(result['canonical_url'], 'https://www.citizen.digital/business/sample-news-n12345')
        self.assertIn('final paragraph', result['article_text'])
        self.assertNotIn('toolbar', result['article_text'])
        self.assertNotIn('footer', result['article_text'])

    def test_august_article_body_layout(self):
        html = HTML.replace('class="article-content-wrapper"', 'class="article-content"').replace('class="the-content"', 'class="js-article-body"')
        result = citizen.parse(html, URL)
        self.assertIsNotNone(result)
        self.assertIn('final paragraph', result['article_text'])

    def test_article_and_legacy_news_discovery(self):
        html = f'<a href="{URL}">One</a><a href="{URL}#top">Duplicate</a><a href="/news/another-story-n54321">Two</a><a href="/news">Section</a><a href="https://example.com/article/test-n99">Other</a>'
        urls = citizen.discover(html, citizen.LISTINGS[0])
        self.assertEqual(len(urls), 2)
        self.assertTrue(all(citizen.accepts(url) for url in urls))

    def test_rejects_live_and_other_publisher_replays(self):
        self.assertFalse(citizen.accepts_fetch('https://citizen.digital/article/test-n99'))
        self.assertFalse(citizen.accepts_fetch('https://web.archive.org/web/20260309182207/https://example.com/article/test-n99'))
        self.assertIsNone(citizen.parse(HTML.replace('https://www.citizen.digital/business/sample-news-n12345', 'https://example.com/article/test-n99'), URL))

    def test_paywall_and_missing_body(self):
        self.assertIsNone(citizen.parse(HTML.replace('&quot;headline&quot;', '&quot;isAccessibleForFree&quot;:false,&quot;headline&quot;'), URL))
        self.assertIsNone(citizen.parse('<h1>No body</h1>', URL))


if __name__ == '__main__':
    unittest.main()
