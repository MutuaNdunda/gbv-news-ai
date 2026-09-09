from pathlib import Path
import unittest

from database.models import Article, ArticleVersion, CollectionRun, CollectionRunScan
from database.repositories.collection_run_scans import TERMINAL_SCAN_STATUSES


class CollectionRunScanModelTests(unittest.TestCase):
    def test_uuid_primary_keys_use_postgresql_server_default(self):
        for model in (CollectionRun, CollectionRunScan, Article, ArticleVersion):
            default = model.__table__.c.id.server_default
            self.assertIsNotNone(default)
            self.assertEqual(str(default.arg), "gen_random_uuid()")

    def test_model_has_required_unique_constraint_and_columns(self):
        table = CollectionRunScan.__table__
        self.assertEqual(table.schema, "public")
        self.assertTrue(any(
            set(constraint.columns.keys()) == {"collection_run_id", "source", "capture_month"}
            for constraint in table.constraints if hasattr(constraint, "columns")
        ))
        self.assertEqual(set(table.columns.keys()), {
            "id", "collection_run_id", "source", "capture_month", "status",
            "index_pages", "candidate_count", "fetch_attempts", "articles_saved",
            "duplicates_skipped", "errors_count", "started_at", "finished_at", "updated_at",
        })

    def test_migration_has_constraints_indexes_and_rls(self):
        sql = Path("migrations/20260909_add_collection_run_scans.sql").read_text()
        for phrase in ("UNIQUE (collection_run_id, source, capture_month)",
                       "collection_run_scans_source_check", "collection_run_scans_status_check",
                       "idx_collection_run_scans_collection_run_id", "idx_collection_run_scans_source",
                       "idx_collection_run_scans_capture_month", "idx_collection_run_scans_status",
                       "ENABLE ROW LEVEL SECURITY"):
            self.assertIn(phrase, sql)
        self.assertNotIn("CREATE POLICY", sql)
        self.assertIn("index_exhausted", TERMINAL_SCAN_STATUSES)
