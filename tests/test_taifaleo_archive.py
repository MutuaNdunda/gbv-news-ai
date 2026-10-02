"""Taifa Leo URL, legacy body/date, structured metadata, and CDX regressions."""
from pathlib import Path
import unittest
from unittest.mock import Mock

from scrapers import taifaleo
from scripts.trial_scraper import candidates

ORIGINAL = "https://taifaleo.nation.co.ke/shule-yapokea-vifaa-vipya/"
ARCHIVE = "https://web.archive.org/web/20221012164549id_/" + ORIGINAL
HTML = (Path(__file__).parent / "fixtures/taifaleo_archive_article.html").read_text()


class TaifaLeoTests(unittest.TestCase):
    def test_legacy_body_title_byline_and_date(self):
        article = taifaleo.parse(HTML, ARCHIVE)
        self.assertEqual(article["source"], "taifaleo")
        self.assertEqual(article["title"], "Shule yapokea vifaa vipya")
        self.assertEqual(article["author"], "MWANDISHI WA MAJARIBIO")
        self.assertEqual(article["published_at"], "2022-10-12T00:00:00")
        self.assertEqual(article["publication_date_precision"], "day")
        self.assertEqual(article["publication_timezone"], "unknown")
        self.assertEqual(article["canonical_url"], ORIGINAL)
        self.assertEqual(article["archive_capture_timestamp"], "20221012164549")
        self.assertEqual(article["language"], "")
        self.assertEqual(article["language_metadata_raw"], "en-US")
        self.assertTrue(article["language_needs_review"])
        self.assertEqual(article["kenya_relevance"], "needs_review")
        self.assertIn("aya ya mwisho", article["article_text"])
        for text in ("NA MWANDISHI", "By Admin", "Habari nyingine", "urambazaji"):
            self.assertNotIn(text, article["article_text"])

    def test_dated_wordpress_article_and_structured_metadata(self):
        original = "https://taifaleo.nation.co.ke/2024/04/07/shule-yapokea-vifaa-vipya/"
        html = '''<html lang="sw"><head><script type="application/ld+json">
        {"@type":"NewsArticle","headline":"Habari ya shule","datePublished":"2024-04-07T10:00:00+03:00","author":{"name":"Mwandishi"},"inLanguage":"sw"}
        </script></head><body><div class="entry-content"><p>Aya ya kwanza.</p><p>Aya ya mwisho.</p></div></body></html>'''
        article = taifaleo.parse(html, "https://web.archive.org/web/20240407100000/" + original)
        self.assertEqual(article["published_at"], "2024-04-07T10:00:00+03:00")
        self.assertEqual(article["language"], "sw")
        self.assertEqual(article["canonical_url"], original)
        self.assertNotIn("publication_timezone", article)

    def test_modern_body_and_publisher_date_metadata(self):
        html = '''<html lang="en-US"><head>
        <meta property="og:title" content="Habari ya majaribio">
        <meta property="og:article:published_time" content="2024-05-22 16:21:17">
        </head><body><div class="meta-author">Na Mwandishi wa majaribio</div>
        <div class="article-content__content"><div class="incontent-ad"><p>Tangazo</p></div>
        <p>Aya ya kwanza.</p><div class="mobile-ad-"><p>Tangazo la simu</p></div>
        <p>Aya ya mwisho.</p><figure><p>Maelezo ya picha</p></figure></div>
        <footer><p>Urambazaji</p></footer></body></html>'''
        article = taifaleo.parse(html, ARCHIVE)
        self.assertEqual(article["published_at"], "2024-05-22T16:21:17")
        self.assertEqual(article["author"], "Mwandishi wa majaribio")
        self.assertEqual(article["publication_timezone"], "unknown")
        self.assertEqual(article["article_text"], "Aya ya kwanza.\n\nAya ya mwisho.")
        self.assertEqual(article["parser_version"], "taifaleo-archive-1.1")

    def test_url_boundaries_and_restricted_content(self):
        for invalid in (
            "https://taifaleo.nation.co.ke/", "https://taifaleo.nation.co.ke/category/habari/",
            "https://taifaleo.nation.co.ke/author/mwandishi/", "https://taifaleo.nation.co.ke/wp-content/file-name/",
            ORIGINAL + "?page=2", ORIGINAL.replace("taifaleo.nation.co.ke", "nation.co.ke"),
            "https://taifaleo.nation.co.ke/2024/02/30/shule-yapokea-vifaa/",
        ):
            self.assertFalse(taifaleo.is_article(invalid), invalid)
        self.assertFalse(taifaleo.accepts_fetch(ORIGINAL))
        self.assertFalse(taifaleo.accepts_fetch(taifaleo.CDX_URL.replace("taifaleo.nation.co.ke", "example.com")))
        self.assertIsNone(taifaleo.parse(HTML.replace("<body>", '<body><aside id="paywall">Jiunge</aside>'), ARCHIVE))
        self.assertIsNone(taifaleo.parse(HTML.replace(ORIGINAL, "https://example.com/other-story/"), ARCHIVE))
        self.assertIsNone(taifaleo.parse("<h1>Hakuna taarifa</h1>", ARCHIVE))

    def test_cdx_discovery_filters_navigation_and_keeps_original_replay(self):
        payload = [["timestamp", "original", "statuscode", "mimetype"],
                   ["20221012164549", ORIGINAL, "200", "text/html"],
                   ["20221012164549", ORIGINAL, "200", "text/html"],
                   ["20221012164549", "https://taifaleo.nation.co.ke/category/habari/", "200", "text/html"]]
        client = Mock()
        client.fetch.return_value = Mock(json=lambda: payload)
        self.assertEqual(list(candidates(taifaleo, client)), [(ARCHIVE, taifaleo.CDX_URL, "wayback_cdx")])
        client.fetch.assert_called_once_with(taifaleo.CDX_URL, stage="CDX_INDEX")
        client.fetch.return_value = None
        with self.assertRaises(RuntimeError):
            list(candidates(taifaleo, client))
        for malformed in ({"error": "denied"}, [["timestamp", "original"]],
                          [["timestamp", "original", "statuscode", "mimetype"], ["bad", ORIGINAL, "200", "text/html"]]):
            with self.assertRaises(ValueError):
                taifaleo.cdx_records(malformed)


if __name__ == "__main__":
    unittest.main()
