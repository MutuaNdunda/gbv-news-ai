"""Original HTML replay keeps publisher parsing and archive boundaries intact."""
from pathlib import Path
import re
import unittest
from unittest.mock import Mock, patch

from scrapers import citizen, kenyans, nation, standard, star, taifaleo, tuko
from scrapers.common import Client


FIXTURES = Path(__file__).parent / "fixtures"
CASES = (
    (nation, "https://nation.africa/kenya/business/sample-news-update-1234567"),
    (citizen, "https://citizen.digital/article/sample-news-n12345"),
    (standard, "https://standardmedia.co.ke/education/article/2001382295/test-story"),
    (star, "https://www.the-star.co.ke/news/2025-12-27-sample-news"),
    (tuko, "https://www.tuko.co.ke/kenya/638082-sample-tuko-story/"),
    (kenyans, "https://www.kenyans.co.ke/news/103100-sample-kenyans-story"),
    (taifaleo, "https://taifaleo.nation.co.ke/shule-yapokea-vifaa-vipya/"),
)


class OriginalReplayTests(unittest.TestCase):
    def test_all_publishers_parse_original_and_rewritten_canonicals(self):
        timestamp = "20260120000000"
        for publisher, original in CASES:
            with self.subTest(source=publisher.SOURCE):
                replay = f"https://web.archive.org/web/{timestamp}/{original}"
                raw_replay = f"https://web.archive.org/web/{timestamp}id_/{original}"
                html = (FIXTURES / f"{publisher.SOURCE}_archive_article.html").read_text()
                expected = publisher.parse(html, replay)
                # Remove archive URL rewriting to simulate original HTML.
                original_html = re.sub(r"https://web\.archive\.org/web/\d{14}/", "", html)
                for body in (html, original_html):
                    article = publisher.parse(body, raw_replay)
                    self.assertTrue(publisher.accepts(raw_replay))
                    self.assertEqual(article["url"], original)
                    self.assertEqual(article["archive_url"], raw_replay)
                    self.assertEqual(article["archive_capture_timestamp"], timestamp)
                    for field in ("title", "published_at", "article_text", "content_hash", "canonical_url"):
                        self.assertEqual(article[field], expected[field])

    def test_original_replay_preserves_queries_and_rejects_unsupported_routes(self):
        original = "https://citizen.digital/article/sample-news-n12345?edition=1"
        replay = "https://web.archive.org/web/20260120000000id_/" + original
        self.assertEqual(citizen.archive_parts(replay), ("20260120000000", original))
        for invalid in (
            replay.replace("id_", "im_"),
            replay.replace("id_", "if_"),
            replay.replace("id_", "*"),
            replay.replace("citizen.digital", "example.com"),
            original,
        ):
            with self.subTest(url=invalid):
                self.assertFalse(citizen.accepts(invalid))

    def test_original_replay_redirect_cannot_leave_publisher(self):
        replay = "https://web.archive.org/web/20260120000000id_/" + CASES[1][1]
        client = Client(citizen.HOSTS, delay=0, url_validator=citizen.accepts)
        for destination in (CASES[1][1], replay.replace("citizen.digital", "example.com")):
            redirect = Mock(status_code=302, headers={"Location": destination})
            with self.subTest(destination=destination), \
                    patch.object(client, "permitted", return_value=True), \
                    patch.object(client, "_request", return_value=redirect) as request:
                self.assertIsNone(client.fetch(replay))
                self.assertEqual(request.call_count, 1)


if __name__ == "__main__":
    unittest.main()
