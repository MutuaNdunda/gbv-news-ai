"""Offline regressions based on the inspected Kenyans.co.ke archive structure."""
from pathlib import Path
import unittest

from scrapers import kenyans

ORIGINAL = "https://www.kenyans.co.ke/news/103100-sample-kenyans-story"
ARCHIVE = "https://web.archive.org/web/20240725030817/" + ORIGINAL
HTML = (Path(__file__).parent / "fixtures/kenyans_archive_article.html").read_text()


class KenyansArchiveTests(unittest.TestCase):
    def test_archive_validation_and_url_rules(self):
        self.assertEqual(kenyans.archive_parts(ARCHIVE), ("20240725030817", ORIGINAL))
        self.assertTrue(kenyans.is_article(ORIGINAL))
        self.assertFalse(kenyans.is_article("https://www.kenyans.co.ke/news"))
        self.assertFalse(kenyans.is_article("https://www.kenyans.co.ke/featured/101553-sponsored"))
        self.assertFalse(kenyans.accepts_fetch(ORIGINAL))
        self.assertFalse(kenyans.accepts_fetch(
            "https://web.archive.org/web/20240725030817/https://example.com/news/103100-story"
        ))

    def test_discovery_and_non_article_rejection(self):
        html = f'<a href="{ORIGINAL}">One</a><a href="{ARCHIVE}">Duplicate</a>' \
               '<a href="/news/103101-second-story">Two</a><a href="/news">Section</a>'
        found = kenyans.discover(html, kenyans.LISTINGS[0])
        self.assertEqual(len(found), 2)
        self.assertTrue(all(kenyans.accepts(url) for url in found))

    def test_parse_metadata_body_canonical_and_provenance(self):
        article = kenyans.parse(HTML, ARCHIVE)
        self.assertEqual(article["source"], "kenyans")
        self.assertEqual(article["title"], "Sample Kenyans article")
        self.assertEqual(article["author"], "Test Writer")
        self.assertEqual(article["published_at"], "2024-07-24T19:52:40+03:00")
        self.assertEqual(article["canonical_url"], ORIGINAL)
        self.assertEqual(article["archive_url"], ARCHIVE)
        self.assertEqual(article["archive_capture_timestamp"], "20240725030817")
        self.assertEqual(article["parser_version"], "kenyans-archive-1.0")
        self.assertIn("Final Kenyans", article["article_text"])

    def test_paywall_foreign_canonical_and_malformed_pages(self):
        paid = HTML.replace('"isAccessibleForFree":"True"', '"isAccessibleForFree":false')
        self.assertIsNone(kenyans.parse(paid, ARCHIVE))
        self.assertIsNone(kenyans.parse(HTML.replace(ORIGINAL, "https://example.com/news/103100-story"), ARCHIVE))
        self.assertIsNone(kenyans.parse("<h1>Missing body</h1>", ARCHIVE))


if __name__ == "__main__":
    unittest.main()
