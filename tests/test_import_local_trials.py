"""Offline local-to-cloud import validation, deduplication, and recovery."""

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.import_local_trials import import_trials
from storage.persistence import CollectionPersistence
from tests.storage_fakes import FakeArticles, FakeObjects, FakeRuns


class LocalImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raw = self.root / "raw"
        self.processed = self.root / "processed"
        (self.raw / "citizen").mkdir(parents=True)
        self.processed.mkdir()
        self.path = self.raw / "citizen/snapshot.html"
        self.path.write_text("<html>Synthetic article</html>")
        text = "Synthetic article body"
        self.item = {"source": "citizen", "url": "https://citizen.digital/news/test-n1",
                     "canonical_url": "https://citizen.digital/news/test-n1",
                     "title": "Synthetic article", "article_text": text,
                     "content_hash": hashlib.sha256(text.encode()).hexdigest(),
                     "scraped_at": "2026-09-01T10:00:00+00:00",
                     "published_at": "2026-08-01T10:00:00+03:00",
                     "parser_version": "local-test", "raw_snapshot_path": str(self.path)}
        self.objects, self.articles, self.runs = FakeObjects(), FakeArticles(), FakeRuns()
        self.services = (CollectionPersistence(self.objects, self.articles), self.articles, self.runs)

    def write(self, *items):
        (self.processed / "citizen.jsonl").write_text(
            "\n".join(json.dumps(item) for item in items) + "\n")

    def run_import(self, **kwargs):
        return import_trials(self.processed, self.raw, services=self.services, **kwargs)

    def test_dry_run_is_offline_and_does_not_modify_input(self):
        self.write(self.item)
        before = self.path.read_bytes()
        with patch("scripts.import_local_trials.build_services", side_effect=AssertionError):
            result = import_trials(self.processed, self.raw, dry_run=True)
        self.assertEqual(result["ready"], 1)
        self.assertEqual(self.objects.writes, [])
        self.assertEqual(self.path.read_bytes(), before)

    def test_repeat_and_content_alias_do_not_create_duplicates(self):
        alias = dict(self.item, canonical_url="https://citizen.digital/news/alias-n2",
                     url="https://citizen.digital/news/alias-n2")
        self.write(self.item, self.item, alias)
        first = self.run_import()
        self.assertEqual((first["saved"], first["duplicates"]), (1, 2))
        count = len(self.objects.data)
        second = self.run_import(run_name="another-import")
        self.assertEqual((second["saved"], second["duplicates"]), (0, 3))
        self.assertEqual(len(self.articles.items), 1)
        self.assertEqual(len(self.objects.data), count + 1)  # new run summary only

    def test_database_failure_can_resume_without_extra_article_objects(self):
        self.item["published_at"] = ""
        self.write(self.item)
        self.articles.fail_persist = True
        first = self.run_import()
        self.assertEqual(first["failed"], 1)
        artifact_keys = {key for key in self.objects.data if key[0] != "runs"}
        self.assertTrue(all("/2026/09/" in name for _, name in artifact_keys))
        self.articles.fail_persist = False
        second = self.run_import()
        self.assertEqual(second["saved"], 1)
        self.assertEqual(artifact_keys, {key for key in self.objects.data if key[0] != "runs"})
        item = self.articles.items[0][0]
        self.assertNotIn("publication_month", item)
        self.assertTrue(item["publication_date_needs_review"])

    def test_legacy_wayback_record_finds_hashed_snapshot(self):
        self.item.pop("raw_snapshot_path")
        self.item["wayback_timestamp"] = "20260801100000"
        replay = f"https://web.archive.org/web/20260801100000id_/{self.item['url']}"
        filename = hashlib.sha1(replay.encode()).hexdigest()[:16] + ".html"
        self.path.rename(self.raw / "citizen" / filename)
        self.write(self.item)
        self.assertEqual(self.run_import()["saved"], 1)
        self.assertEqual(self.articles.items[0][0]["requested_url"], replay)
        self.assertNotIn("archive_capture_timestamp", self.articles.items[0][0])

    def test_invalid_hash_missing_raw_and_off_publisher_are_not_uploaded(self):
        self.write(dict(self.item, content_hash="incorrect"),
                   dict(self.item, raw_snapshot_path=str(self.raw / "missing.html")),
                   dict(self.item, canonical_url="https://example.com/story"))
        result = self.run_import()
        self.assertEqual(result["failed"], 3)
        self.assertEqual(self.articles.items, [])
        self.assertFalse(any(role != "runs" for role, _ in self.objects.writes))

    def test_symlink_outside_raw_root_is_rejected(self):
        outside = self.root / "outside.html"
        outside.write_text("sensitive synthetic data")
        self.path.unlink()
        self.path.symlink_to(outside)
        self.write(self.item)
        self.assertEqual(self.run_import()["failed"], 1)

    def test_bad_json_does_not_prevent_following_valid_record(self):
        self.write(self.item)
        path = self.processed / "citizen.jsonl"
        path.write_text("{bad json\n" + path.read_text())
        result = self.run_import()
        self.assertEqual((result["saved"], result["failed"]), (1, 1))
        self.assertEqual(result["errors"][0]["line"], 1)

    def test_individual_json_with_legacy_raw_field_is_imported(self):
        item = dict(self.item)
        item["raw_snapshot"] = item.pop("raw_snapshot_path")
        (self.processed / "article.json").write_text(json.dumps(item))
        result = self.run_import()
        self.assertEqual((result["checked"], result["saved"], result["failed"]), (1, 1, 0))

    def test_mixed_formats_deduplicate_and_skip_manifests(self):
        self.write(self.item)
        (self.processed / "article.json").write_text(json.dumps(self.item))
        (self.processed / "citizen.manifest.json").write_text("not article JSON")
        (self.processed / "progress.json").write_text(json.dumps({"status": "completed"}))
        result = self.run_import()
        self.assertEqual((result["checked"], result["saved"], result["duplicates"]), (2, 1, 1))

    def test_individual_json_source_filter_and_error_file_reference(self):
        self.write(self.item)
        other = dict(self.item, source="nation")
        (self.processed / "bad-nation.json").write_text(json.dumps(other))
        result = self.run_import(sources=["citizen"])
        self.assertEqual(result["checked"], 1)
        result = self.run_import(run_name="all-sources")
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["errors"][0]["file"], "bad-nation.json")

    def test_corporate_nation_trial_retains_scope_and_requires_explicit_marker(self):
        (self.raw / "nation").mkdir()
        raw = self.raw / "nation/corporate.html"
        raw.write_text("<html>Corporate fixture</html>")
        item = dict(self.item, source="nation", content_scope="corporate_news",
                    url="https://www.nationmedia.com/news/test",
                    canonical_url="https://www.nationmedia.com/news/test",
                    raw_snapshot_path=str(raw))
        (self.processed / "corporate.json").write_text(json.dumps(item))
        self.assertEqual(self.run_import()["saved"], 1)
        self.assertEqual(self.articles.items[0][0]["content_scope"], "corporate_news")
        item.pop("content_scope")
        (self.processed / "corporate.json").write_text(json.dumps(item))
        self.assertEqual(self.run_import()["failed"], 1)

    def test_invalid_publication_date_keeps_raw_metadata_and_stable_object_month(self):
        self.item["published_at"] = "invalid date"
        self.write(self.item)
        self.assertEqual(self.run_import()["saved"], 1)
        item = self.articles.items[0][0]
        self.assertEqual(item["published_at_raw"], "invalid date")
        self.assertEqual(item["published_at"], "")
        self.assertNotIn("publication_month", item)
        self.assertTrue(all("/2026/09/" in name for role, name in self.objects.data if role != "runs"))


if __name__ == "__main__":
    unittest.main()
