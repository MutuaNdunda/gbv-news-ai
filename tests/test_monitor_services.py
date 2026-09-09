import unittest
from unittest.mock import MagicMock
from uuid import uuid4

from app.services.article_service import ArticleService
from app.services.dashboard_service import DashboardService
from app.services.run_service import RunService


def sessions_with(session):
    factory = MagicMock()
    factory.return_value.__enter__.return_value = session
    return factory


class MonitorServiceTests(unittest.TestCase):
    def test_dashboard_uses_grouped_aggregate_queries(self):
        session = MagicMock()
        session.scalar.side_effect = [1, 2, 3, 1, 0]
        source_result, month_result, runs_result, activity_result = [MagicMock() for _ in range(4)]
        source_result.all.return_value = [("citizen", 1)]
        month_result.all.return_value = []
        runs_result.scalars.return_value.all.return_value = []
        activity_result.all.return_value = []
        session.execute.side_effect = [source_result, month_result, runs_result, activity_result]
        result = DashboardService(sessions_with(session)).overview()
        sql = [str(call.args[0]) for call in session.execute.call_args_list[:2]]
        self.assertTrue(all("GROUP BY" in statement for statement in sql))
        self.assertEqual(result["totals"]["articles"], 1)

    def test_article_search_builds_one_paginated_query_with_version_filters(self):
        session = MagicMock()
        session.scalar.return_value = 0
        article_result, run_result, parser_result = MagicMock(), MagicMock(), MagicMock()
        article_result.scalars.return_value.all.return_value = []
        run_result.all.return_value = []
        parser_result.scalars.return_value.all.return_value = []
        session.execute.side_effect = [article_result, run_result, parser_result]
        ArticleService(sessions_with(session)).list({
            "q": "example", "source": "citizen", "month": "2026-08",
            "date": "", "run_id": str(uuid4()), "parser_version": "citizen-test",
            "kenya_relevance": "needs_review",
        })
        sql = str(session.execute.call_args_list[0].args[0])
        self.assertIn("EXISTS", sql)
        self.assertIn("lower(public.articles.title) LIKE", sql)
        self.assertIn("article_versions.parser_version", sql)

    def test_run_detail_queries_scans_and_version_count(self):
        session = MagicMock()
        run = object()
        session.get.return_value = run
        scans = MagicMock()
        scans.scalars.return_value.all.return_value = [object()]
        session.execute.return_value = scans
        session.scalar.return_value = 4
        result = RunService(sessions_with(session)).detail(uuid4())
        self.assertIs(result["run"], run)
        self.assertEqual(result["version_count"], 4)
        self.assertEqual(len(result["scans"]), 1)


if __name__ == "__main__":
    unittest.main()
