from datetime import date, datetime, timezone
from types import SimpleNamespace
import unittest
from uuid import uuid4

from app import create_app


NOW = datetime.now(timezone.utc)
RUN_ID = uuid4()
ARTICLE_ID = uuid4()
run = SimpleNamespace(id=RUN_ID, run_name="test-run", status="running",
                      start_month=date(2026, 1, 1), end_month=date(2026, 8, 1),
                      started_at=NOW, finished_at=None, configuration={"kind": "monthly"})
article = SimpleNamespace(id=ARTICLE_ID, article_id="a" * 64, title="Test article",
                          source="citizen", publisher_name="Citizen Digital",
                          canonical_url="https://citizen.digital/news/test-n1",
                          published_at=NOW, published_at_raw=None, kenya_relevance="needs_review")
version = SimpleNamespace(parser_version="citizen-test", processing_status="indexed",
                          content_hash="b" * 64, scraped_at=NOW, requested_url="https://example.test",
                          archive_url=None, discovery_method="wayback_cdx", discovery_url="https://example.test/cdx",
                          http_status=200, raw_object_uri="gs://raw/object", raw_object_generation="1",
                          processed_object_uri="gs://processed/object", processed_object_generation="2")
scan = SimpleNamespace(source="citizen", capture_month=date(2026, 8, 1), status="running",
                       index_pages=1, candidate_count=5, fetch_attempts=3, articles_saved=2,
                       duplicates_skipped=1, errors_count=0, started_at=NOW, finished_at=None)


class FakeDashboard:
    def overview(self):
        return {"totals": {"articles": 1, "versions": 1, "runs": 1,
                            "active_runs": 1, "problem_runs": 0},
                "by_source": [("citizen", 1)], "by_month": [(date(2026, 8, 1), 1)],
                "recent_runs": [run], "activity": [(version, article)]}


class FakeRuns:
    def list(self, page, per_page):
        return [(run, 1, 0, 1)], 1

    def detail(self, value):
        return {"run": run, "scans": [scan], "version_count": 1} if value == RUN_ID else None


class FakeArticles:
    def list(self, filters, page, per_page):
        self.filters = filters
        return [article], 1, [(RUN_ID, "test-run")], ["citizen-test"]

    def detail(self, value):
        return {"article": article, "versions": [(version, "test-run")]} if value == ARTICLE_ID else None


class FakeHealth:
    def __init__(self, ok=True): self.ok = ok
    def health(self):
        return {"database": self.ok, "tables": self.ok, "raw": self.ok,
                "processed": self.ok, "runs": self.ok, "ok": self.ok}


class MonitorRouteTests(unittest.TestCase):
    def make_app(self, health=True):
        articles = FakeArticles()
        services = {"dashboard": FakeDashboard(), "runs": FakeRuns(),
                    "articles": articles, "health": FakeHealth(health)}
        return create_app({"TESTING": True, "PER_PAGE": 10}, services), articles

    def test_read_only_pages_return_expected_statuses(self):
        app, _ = self.make_app()
        client = app.test_client()
        for path in ("/", "/runs", f"/runs/{RUN_ID}", "/articles",
                     f"/articles/{ARTICLE_ID}", "/health"):
            with self.subTest(path=path):
                self.assertEqual(client.get(path).status_code, 200)
        self.assertEqual(client.get(f"/runs/{uuid4()}").status_code, 404)
        self.assertEqual(client.get(f"/articles/{uuid4()}").status_code, 404)

    def test_article_filters_are_forwarded(self):
        app, articles = self.make_app()
        response = app.test_client().get("/articles?q=Test&source=citizen&month=2026-08&parser_version=citizen-test&kenya_relevance=needs_review")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(articles.filters["q"], "Test")
        self.assertEqual(articles.filters["month"], "2026-08")
        self.assertEqual(articles.filters["parser_version"], "citizen-test")

    def test_articles_source_filter_lists_all_publishers(self):
        app, _ = self.make_app()
        response = app.test_client().get("/articles")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        for source in ("nation", "citizen", "standard", "star", "tuko", "kenyans"):
            self.assertIn(f">{source}</option>", html)

    def test_health_returns_503_when_a_read_check_fails(self):
        app, _ = self.make_app(False)
        self.assertEqual(app.test_client().get("/health").status_code, 503)


if __name__ == "__main__":
    unittest.main()
