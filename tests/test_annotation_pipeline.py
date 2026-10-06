"""Pipeline persistence, current-version gating, retries, and historical lineage."""

from contextlib import nullcontext
from dataclasses import asdict
import json
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

from sqlalchemy.exc import OperationalError

from annotations.service import load_article, run_annotation_pipeline
from annotations.schemas import DEFAULT_CONFIG
from database.repositories.annotations import AnnotationLease, AnnotationLockLost, AnnotationRepository, current_annotations
from scripts.run_annotations import main
from tests.test_annotation_rules import valid_article


class FakeRepository:
    def __init__(self, candidates):
        self.candidates, self.results, self.runs = candidates, [], {}

    def lock(self): return nullcontext()

    def ensure_l2_schema(self): pass

    def create_run(self, layers, methods, trigger, collection_run_id, configuration):
        run_id = uuid4()
        self.runs[run_id] = {"layers": layers, "methods": methods, "trigger": trigger, "configuration": configuration}
        return run_id

    def select_candidates(self, layers, methods, limit, article_ids, collection_run_id, only_pending):
        selected = []
        for item in self.candidates:
            if article_ids and item["article_id"] not in article_ids: continue
            l0 = self.latest(item["id"], "L0", methods["L0"])
            l1 = self.latest(item["id"], "L1", methods["L1"], l0.id if l0 else None)
            if (not only_pending or ("L0" in layers and l0 is None)
                    or ("L1" in layers and l1 is None and ("L0" not in layers or l0 and l0.label == "valid"))):
                selected.append(item)
        return selected if limit is None else selected[:limit]

    def set_selection(self, run_id, candidates): self.runs[run_id]["selected"] = [item["id"] for item in candidates]

    def latest(self, version_id, layer, method_version, prerequisite_id=None):
        return next((item for item in reversed(self.results) if item.article_version_id == version_id
                     and item.layer == layer and item.method_version == method_version
                     and (layer != "L1" or item.prerequisite_annotation_id == prerequisite_id)), None)

    def current_for_candidates(self, version_ids, methods):
        current = {}
        for version_id in version_ids:
            l0 = self.latest(version_id, "L0", methods["L0"])
            if l0:
                current[(version_id, "L0")] = l0
                if l0.label == "valid":
                    l1 = self.latest(version_id, "L1", methods["L1"], l0.id)
                    if l1:
                        current[(version_id, "L1")] = l1
        return current

    def persist(self, candidate, run_id, result, prerequisite_id=None):
        item = SimpleNamespace(**asdict(result), id=uuid4(), article_id=candidate["article_id"],
                               article_version_id=candidate["id"], annotation_run_id=run_id,
                               prerequisite_annotation_id=prerequisite_id)
        self.results.append(item)
        return item

    def checkpoint(self, run_id, summary, status="running"):
        self.runs[run_id]["summary"] = json.loads(json.dumps(summary))
        self.runs[run_id]["status"] = status


def candidate():
    item = valid_article()
    return {"id": uuid4(), "article_id": uuid4(), "metadata": {key: item.get(key) for key in (
        "source", "title", "canonical_url", "published_at", "content_scope")},
        **{key: item[key] for key in ("raw_object_uri", "processed_object_uri", "content_hash", "parser_version")},
        "processed_object_generation": "123"}


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.record = valid_article()
        self.repository = FakeRepository([candidate()])
        self.objects = Mock(buckets={"processed": "processed"})
        self.objects.read_json.return_value = self.record

    def run_pipeline(self, **kwargs):
        return run_annotation_pipeline(services=(self.repository, self.objects), **kwargs)

    def test_l0_persists_and_valid_l0_allows_l1_with_exact_lineage(self):
        summary = self.run_pipeline()
        self.assertEqual(summary["success"], 1)
        self.assertEqual([item.layer for item in self.repository.results], ["L0", "L1"])
        self.assertEqual(self.repository.results[1].prerequisite_annotation_id, self.repository.results[0].id)
        self.objects.read_json.assert_called_once_with("processed", "test.json", generation="123")

    def test_l1_is_gated_for_both_invalid_and_needs_review(self):
        for updates in ({"title": ""}, {"published_at": "bad date"}):
            self.setUp()
            self.objects.read_json.return_value = dict(valid_article(), **updates)
            result = self.run_pipeline()
            self.assertEqual(len(self.repository.results), 1)
            self.assertEqual(result["layers"]["L1"]["skipped_l0"], 1)

    def test_only_l1_does_not_silently_run_l0(self):
        result = self.run_pipeline(layers=["L1"])
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(result["layers"]["L1"]["skipped_l0"], 1)
        self.assertEqual(self.repository.results, [])
        self.objects.read_json.assert_not_called()

    def test_pending_repeat_and_force_preserve_previous_results(self):
        self.run_pipeline()
        original = list(self.repository.results)
        repeated = self.run_pipeline()
        self.assertEqual(repeated["requested"], 0)
        self.assertEqual(len(self.repository.results), 2)
        self.run_pipeline(only_pending=False)
        self.assertEqual(len(self.repository.results), 4)
        self.assertEqual(self.repository.results[:2], original)
        self.assertNotEqual(self.repository.results[2].id, original[0].id)

    def test_forced_l0_invalidates_old_l1_current_gate(self):
        self.run_pipeline()
        old_l1 = self.repository.results[1]
        self.run_pipeline(layers=["L0"], only_pending=False)
        self.run_pipeline(layers=["L1"])
        self.assertEqual(len(self.repository.results), 4)
        self.assertNotEqual(self.repository.results[-1].prerequisite_annotation_id, old_l1.prerequisite_annotation_id)

    def test_one_article_failure_does_not_abort_following_record_or_log_contents(self):
        self.repository.candidates.append(candidate())
        self.objects.read_json.side_effect = [RuntimeError("SECRET sensitive article content"), self.record]
        with self.assertLogs("annotations.service", level="INFO") as logs:
            result = self.run_pipeline()
        self.assertEqual((result["requested"], result["processed"], result["success"], result["failed"]), (2, 2, 1, 1))
        self.assertEqual(result["status"], "completed_with_errors")
        self.assertNotIn("SECRET", str(logs.output) + str(result))
        self.assertIn("annotation_run_completed", str(logs.output))

    def test_missing_processed_object_is_persisted_invalid_l0(self):
        self.objects.read_json.return_value = None
        result = self.run_pipeline()
        self.assertEqual(result["failed"], 0)
        self.assertEqual(self.repository.results[0].label, "invalid")
        self.assertIn("missing_processed_object", self.repository.results[0].reason_codes)

    def test_all_articles_fail_marks_run_failed_and_l1_failure_uses_correct_layer(self):
        self.run_pipeline(layers=["L0"])
        self.objects.read_json.side_effect = RuntimeError("unavailable")
        result = self.run_pipeline(layers=["L1"])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["layers"]["L1"]["failed"], 1)
        self.assertEqual(result["errors"][0]["layer"], "L1")

    def test_forced_invalid_l0_keeps_history_but_blocks_new_l1(self):
        self.run_pipeline()
        old_results = list(self.repository.results)
        self.objects.read_json.return_value = dict(self.record, title="")
        result = self.run_pipeline(only_pending=False)
        self.assertEqual(len(self.repository.results), 3)
        self.assertEqual(self.repository.results[:2], old_results)
        self.assertEqual(self.repository.results[-1].label, "invalid")
        self.assertEqual(result["layers"]["L1"]["skipped_l0"], 1)

    def test_lineage_mismatch_invalid_and_wrong_bucket_rejected(self):
        self.objects.read_json.return_value = dict(self.record, content_hash="b" * 64)
        self.run_pipeline()
        self.assertIn("content_hash_lineage_mismatch", self.repository.results[0].reason_codes)
        item = candidate()
        item["processed_object_uri"] = "gs://other-bucket/private.json"
        with self.assertRaises(ValueError): load_article(item, self.objects)

    def test_cli_uses_shared_service_and_handles_force(self):
        with patch("scripts.run_annotations.run_annotation_pipeline", return_value={"failed": 0}) as run, \
                patch("scripts.run_annotations.logging.basicConfig"), \
                patch("builtins.print"):
            self.assertEqual(main(["--layer", "l0,l1", "--limit", "20", "--force"]), 0)
            self.assertEqual(run.call_args.args[:2], (["l0", "l1"], 20))
            self.assertFalse(run.call_args.args[4])

    def test_repository_sql_resolves_current_l1_against_current_valid_l0(self):
        sql = str(current_annotations({"L0": "l0-v1.0", "L1": "l1-v1.0"}))
        self.assertIn("row_number() OVER", sql)
        self.assertIn("prerequisite_annotation_id", sql)
        self.assertIn("label =", sql)
        sessions = MagicMock()
        session = sessions.return_value.__enter__.return_value
        session.execute.return_value.all.return_value = []
        AnnotationRepository(sessions).select_candidates(["L0", "L1"], {"L0": "l0-v1.0", "L1": "l1-v1.0"}, limit=20)
        statement = str(session.execute.call_args.args[0])
        self.assertIn("EXISTS", statement)
        self.assertIn("LIMIT", statement)

    def test_lock_uses_autocommit_and_cleanup_disconnect_does_not_mask_success(self):
        sessions = MagicMock()
        engine = sessions.kw["bind"]
        engine.url.host, engine.url.port = "session.pooler.test", 5432
        connection = engine.connect.return_value.execution_options.return_value.__enter__.return_value
        initial = Mock()
        initial.one.return_value = (True, 123)
        heartbeat = Mock()
        heartbeat.one.return_value = (123, True)
        disconnected = OperationalError("synthetic", {}, RuntimeError("disconnected"), connection_invalidated=True)
        connection.execute.side_effect = [initial, heartbeat, disconnected]
        with self.assertLogs("annotations.service", level="WARNING") as logs:
            with AnnotationRepository(sessions).lock() as lease:
                lease.check()
        engine.connect.return_value.execution_options.assert_called_once_with(isolation_level="AUTOCOMMIT")
        connection.invalidate.assert_called_once()
        self.assertIn("annotation_lock_release_failed", str(logs.output))

    def test_lost_or_changed_lock_connection_stops_processing(self):
        connection = Mock()
        connection.execute.return_value.one.return_value = (999, True)
        with self.assertRaises(AnnotationLockLost):
            AnnotationLease(connection, 123).check()
        connection.execute.side_effect = OperationalError("synthetic", {}, RuntimeError("disconnected"))
        with self.assertRaises(AnnotationLockLost):
            AnnotationLease(connection, 123).check()

    def test_transaction_pooler_is_rejected_for_session_locks(self):
        sessions = MagicMock()
        sessions.kw["bind"].url.host, sessions.kw["bind"].url.port = "transaction.pooler.test", 6543
        with self.assertRaises(RuntimeError):
            with AnnotationRepository(sessions).lock():
                self.fail("Unsafe transaction pooling was accepted")

    def test_pipeline_stops_after_lock_loss_before_persist_and_keeps_counters(self):
        self.repository.candidates.append(candidate())
        lease = Mock()
        lease.check.side_effect = [None, AnnotationLockLost("synthetic")]
        self.repository.lock = Mock(return_value=nullcontext(lease))
        with self.assertRaises(AnnotationLockLost):
            self.run_pipeline()
        self.assertEqual(self.repository.results, [])
        run = next(iter(self.repository.runs.values()))
        self.assertEqual(run["status"], "failed")
        self.assertEqual(run["summary"]["processed"], 1)
        self.assertEqual(run["summary"]["failed"], 1)

    def test_runner_uses_batch_gate_snapshot_without_per_article_lookup(self):
        self.repository.candidates.append(candidate())
        fetch = self.repository.current_for_candidates
        def snapshot(version_ids, methods):
            current = fetch(version_ids, methods)
            self.repository.latest = Mock(side_effect=AssertionError("per-article lookup"))
            return current
        self.repository.current_for_candidates = Mock(side_effect=snapshot)
        result = self.run_pipeline()
        self.assertEqual(result["success"], 2)
        self.assertEqual(result["layers"]["L1"]["processed"], 2)
        self.repository.current_for_candidates.assert_called_once()
        self.repository.latest.assert_not_called()

    def test_repository_batch_uses_one_current_query_and_empty_selection_is_free(self):
        sessions = MagicMock()
        row = SimpleNamespace(article_version_id=uuid4(), layer="L0")
        session = sessions.return_value.__enter__.return_value
        session.scalars.return_value.all.return_value = [row]
        repository = AnnotationRepository(sessions)
        self.assertEqual(repository.current_for_candidates([], {}), {})
        sessions.assert_not_called()
        current = repository.current_for_candidates([row.article_version_id], {"L0": "l0-v1.0", "L1": "l1-v1.0"})
        self.assertIs(current[(row.article_version_id, "L0")], row)
        session.scalars.assert_called_once()

    def test_l1_refuses_missing_or_mismatched_processed_input_after_valid_l0(self):
        changed_records = [None, dict(valid_article(), parser_version="different"),
                           dict(valid_article(), article_text="different body"),
                           dict(valid_article(), article_text=None)]
        for changed in changed_records:
            with self.subTest(changed=changed is None):
                self.setUp()
                self.run_pipeline(layers=["L0"])
                self.objects.read_json.return_value = changed
                result = self.run_pipeline(layers=["L1"])
                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["failed"], 1)
                self.assertEqual(len(self.repository.results), 1)
                self.assertEqual(self.repository.results[0].label, "valid")


if __name__ == "__main__": unittest.main()
