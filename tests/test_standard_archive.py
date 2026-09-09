from pathlib import Path
import unittest
from unittest.mock import Mock
from scrapers import standard
from scripts.trial_scraper import candidates

ORIGINAL = 'https://standardmedia.co.ke/education/article/2001382295/test-story'
URL = 'https://web.archive.org/web/20200812220757/' + ORIGINAL
HTML = (Path(__file__).parent / 'fixtures/standard_archive_article.html').read_text()


class StandardArchiveTests(unittest.TestCase):
    def test_direct_text_and_publication_timezone(self):
        article = standard.parse(HTML, URL)
        self.assertEqual(article['published_at'], '2020-08-13T00:00:00+03:00')
        self.assertEqual(article['canonical_url'], ORIGINAL)
        self.assertEqual(article['archive_capture_timestamp'], '20200812220757')
        self.assertEqual(article['source'], 'standard')
        self.assertIn('First paragraph', article['article_text'])
        self.assertIn('Final paragraph', article['article_text'])
        for text in ('SEE ALSO', 'Related headlines', 'caption', 'controls', 'toolbar'):
            self.assertNotIn(text, article['article_text'])

    def test_bounded_section_expansion_and_round_robin(self):
        section = 'https://standardmedia.co.ke/category/1/national'
        second = 'https://standardmedia.co.ke/national/article/2001382000/second'
        third = 'https://standardmedia.co.ke/national/article/2001382001/third'
        home = f'<a href="{ORIGINAL}">One</a><a href="{third}">Three</a><a href="{section}">Section</a>'
        page = f'<a href="{second}">Two</a><a href="{ORIGINAL}">Duplicate</a><a href="?page=2">Next</a>'
        client = Mock()
        client.fetch.side_effect = [Mock(content=home.encode(), url=standard.LISTINGS[0]),
                                   Mock(content=page.encode(), url='https://web.archive.org/web/20200812220609/' + section)]
        found = list(candidates(standard, client, max_pages=2))
        self.assertEqual(client.fetch.call_count, 2)
        self.assertEqual([standard.archive_parts(x[0])[1] for x in found], [ORIGINAL, second, third])
        self.assertIn('/category/1/national', found[1][1])

    def test_pagination_query_preserved(self):
        base = 'https://web.archive.org/web/20200812220609/https://standardmedia.co.ke/category/1/national'
        from scrapers.archive import discover_archive
        links = discover_archive('<a href="?page=2">Next</a>', base, standard.PUBLISHER_HOSTS, standard.is_listing)
        self.assertEqual(len(links), 1)
        self.assertTrue(standard.archive_parts(links[0])[1].endswith('?page=2'))
        self.assertFalse(standard.is_listing('https://standardmedia.co.ke/category/1/national?redirect=elsewhere'))

    def test_foreign_and_live_urls_and_paywalls_rejected(self):
        self.assertFalse(standard.accepts_fetch(ORIGINAL))
        self.assertFalse(standard.accepts_fetch('https://web.archive.org/web/20200812220757/https://example.com/article/123/test'))
        self.assertIsNone(standard.parse(HTML.replace('<body>', '<body><aside id="paywall">Subscribe</aside>'), URL))
        self.assertIsNone(standard.parse('<h1>No body</h1>', URL))


if __name__ == '__main__':
    unittest.main()
