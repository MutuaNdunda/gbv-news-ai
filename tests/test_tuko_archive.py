"""Offline regressions based on the inspected Tuko archive structure."""
from pathlib import Path
import unittest

from scrapers import tuko

ORIGINAL = "https://www.tuko.co.ke/kenya/638082-sample-tuko-story/"
ARCHIVE = "https://web.archive.org/web/20260831091459/" + ORIGINAL
HTML = (Path(__file__).parent / "fixtures/tuko_archive_article.html").read_text()


class TukoArchiveTests(unittest.TestCase):
    def test_archive_validation_and_url_rules(self):
        self.assertEqual(tuko.archive_parts(ARCHIVE), ("20260831091459", ORIGINAL))
        self.assertTrue(tuko.is_article(ORIGINAL))
        self.assertTrue(tuko.is_article("https://tuko.co.ke/people/family/638077-another-story/"))
        self.assertFalse(tuko.is_article("https://www.tuko.co.ke/kenya/"))
        self.assertFalse(tuko.accepts_fetch(ORIGINAL))
        self.assertFalse(tuko.accepts_fetch(
            "https://web.archive.org/web/20260831091459/https://example.com/kenya/638082-story/"
        ))

    def test_discovery_and_non_article_rejection(self):
        html = f'<a href="{ORIGINAL}">One</a><a href="{ARCHIVE}">Duplicate</a>' \
               '<a href="/politics/638084-second-story/">Two</a><a href="/kenya/">Section</a>'
        found = tuko.discover(html, tuko.LISTINGS[0])
        self.assertEqual(len(found), 2)
        self.assertTrue(all(tuko.accepts(url) for url in found))

    def test_parse_metadata_body_canonical_and_provenance(self):
        article = tuko.parse(HTML, ARCHIVE)
        self.assertEqual(article["source"], "tuko")
        self.assertEqual(article["title"], "Sample Tuko story")
        self.assertEqual(article["author"], "Test Reporter")
        self.assertEqual(article["published_at"], "2026-08-30T20:17:50+03:00")
        self.assertEqual(article["canonical_url"], ORIGINAL)
        self.assertEqual(article["archive_url"], ARCHIVE)
        self.assertEqual(article["archive_capture_timestamp"], "20260831091459")
        self.assertEqual(article["parser_version"], "tuko-archive-1.0")
        self.assertIn("Final Tuko", article["article_text"])
        self.assertNotIn("PAY ATTENTION", article["article_text"])
        self.assertNotIn("Read also", article["article_text"])

    def test_paywall_foreign_canonical_and_malformed_pages(self):
        self.assertIsNone(tuko.parse(HTML.replace("<h1>", '<span class="premium">Premium</span><h1>'), ARCHIVE))
        self.assertIsNone(tuko.parse(HTML.replace(ORIGINAL, "https://example.com/kenya/638082-story/"), ARCHIVE))
        self.assertIsNone(tuko.parse("<h1>Missing body</h1>", ARCHIVE))


if __name__ == "__main__":
    unittest.main()
