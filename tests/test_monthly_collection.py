"""Offline checks for month attribution, GCS reports/cache, and resumability."""

from datetime import datetime, timezone
import hashlib
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from scripts import collect_monthly as monthly
from scrapers import citizen
from storage.persistence import CollectionPersistence
from tests.storage_fakes import FakeArticles, FakeObjects, FakeRuns, FakeScans


class MonthlyTests(unittest.TestCase):
    def test_reverse_months_and_dates(self):
        self.assertEqual(monthly.months_descending("2026-01", "2026-08"),
                         [f"2026-{month:02d}" for month in range(8, 0, -1)])
        self.assertEqual(monthly.publication_month("2026-01-31T23:50:00-03:00"), "2026-01")
        self.assertIsNone(monthly.publication_month("2026-02-30"))
        self.assertIsNone(monthly.publication_month("unknown"))
        with self.assertRaises(ValueError):
            monthly.months_descending("2026-08", "2026-01")

    def test_index_resume_and_calendar(self):
        rows, key = monthly.parse_index([
            ["timestamp", "original"],
            ["20260801000000", "https://example.com/a"], [], ["token%21"],
        ])
        self.assertEqual(len(rows), 1)
        self.assertEqual(key, "token%21")
        publisher = Mock(PUBLISHER_HOSTS=("citizen.digital",))
        query = parse_qs(urlsplit(monthly.index_url(publisher, "2026-02", key)).query)
        self.assertEqual(query["to"], ["20260228"])
        self.assertEqual(query["resumeKey"], ["token!"])
        with self.assertRaises(ValueError):
            monthly.parse_index({"error": "denied"})

    def test_citizen_known_good_monthly_cdx_query_is_preserved(self):
        query = parse_qs(urlsplit(monthly.index_url(citizen, "2026-08")).query)
        self.assertEqual(query["url"], ["citizen.digital"])
        self.assertEqual(query["matchType"], ["domain"])
        self.assertEqual(query["from"], ["20260801"])
        self.assertEqual(query["to"], ["20260831"])
        self.assertEqual(query["output"], ["json"])
        self.assertEqual(query["fl"], ["timestamp,original"])
        self.assertEqual(query["filter"], ["statuscode:200", "mimetype:text/html"])
        self.assertEqual(query["collapse"], ["urlkey"])
        self.assertEqual(query["limit"], ["1000"])
        self.assertEqual(query["showResumeKey"], ["true"])

    def test_reports_cache_and_resume_are_gcs_backed(self):
        objects, articles, runs = FakeObjects(), FakeArticles(), FakeRuns()
        persistence = CollectionPersistence(objects, articles)
        publishers = {}
        for name in ("nation", "citizen", "standard", "star"):
            publisher = Mock(PUBLISHER_HOSTS=(name + ".example",))
            publisher.is_article = lambda url: True
            publisher.accepts = lambda url: True

            def parse(html, url, name=name):
                capture = url.split("/web/")[1][:6]
                month = "2026-01" if capture == "202608" else capture[:4] + "-" + capture[4:]
                original = url.split("/", 5)[5]
                text = "Synthetic " + url
                return {"source": name, "url": original, "canonical_url": original,
                        "published_at": month + "-15T12:00:00+03:00",
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "article_text": text,
                        "content_hash": hashlib.sha256(text.encode()).hexdigest(),
                        "parser_version": name + "-test", "content_scope": "news_reporting"}

            publisher.parse = parse
            publishers[name] = publisher

        order = []

        def fetch(url):
            if "/cdx/" in url:
                query = parse_qs(urlsplit(url).query)
                host, capture = query["url"][0], query["from"][0][:6]
                order.append((host, capture))
                return Mock(json=lambda: [["timestamp", "original"],
                                           [capture + "15000000", f"https://{host}/article/{capture}"]])
            return Mock(url=url, content=b"synthetic", headers={"Content-Type": "text/html"}, status_code=200)

        client = Mock(fetch=Mock(side_effect=fetch), last_request=0, user_agent="Test",
                      last_failure=None)
        config = {"kind": "monthly", "start_month": "2026-01", "end_month": "2026-08",
                  "sources": list(publishers), "delay": 2.0,
                  "max_index_pages": 0, "max_fetches_per_month": 0}
        scans = FakeScans()
        services = (persistence, articles, runs, scans)
        with patch.object(monthly, "SOURCES", publishers), patch.object(monthly, "Client", return_value=client):
            state = monthly.run(config, "test-run", services)
            self.assertEqual(state["status"], "index_scans_finished")
            self.assertIn(("runs", "runs/test-run/progress.json"), objects.data)
            self.assertIn(("runs", "runs/test-run/monthly_counts.csv"), objects.data)
            self.assertTrue(any("cdx-cache" in name for role, name in objects.data if role == "runs"))
            first_order = list(order)
            monthly.run(config, "test-run", services)
            self.assertEqual(order, first_order)
            self.assertEqual(len(articles.versions), 32)
            self.assertEqual(len(scans.rows), 32)
            self.assertTrue(all(row["status"] == "index_exhausted" for row in scans.rows.values()))

    def test_nation_cdx_timeout_records_context_and_is_not_empty_coverage(self):
        objects, articles, runs = FakeObjects(), FakeArticles(), FakeRuns()
        services = (CollectionPersistence(objects, articles), articles, runs, FakeScans())
        config = {"kind": "monthly", "start_month": "2026-01", "end_month": "2026-08",
                  "sources": ["nation"], "delay": 2.0,
                  "max_index_pages": 0, "max_fetches_per_month": 0}
        index_client = Mock(last_request=0, user_agent="Test", last_failure={
            "kind": "ReadTimeout", "stage": "CDX_INDEX",
            "host": "web.archive.org", "url": monthly.CDX,
            "http_status": None,
        })
        index_client.fetch.return_value = None
        article_client = Mock(last_request=0)
        with patch.object(monthly, "Client", side_effect=[index_client, article_client]):
            result = monthly.run(config, "failure-run", services)
        requested = index_client.fetch.call_args.args[0]
        query = parse_qs(urlsplit(requested).query)
        self.assertEqual(query["url"], ["nation.africa"])
        self.assertEqual(query["matchType"], ["domain"])
        self.assertEqual(result["status"], "paused_index_unavailable")
        self.assertEqual(result["scans"]["nation/2026-08"]["status"], "index_failed")
        self.assertEqual(result["scans"]["nation/2026-08"]["error"]["stage"],
                         "CDX_INDEX")
        self.assertEqual(result["scans"]["nation/2026-08"]["failed"], 1)
        self.assertEqual(result["scans"]["nation/2026-01"]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
