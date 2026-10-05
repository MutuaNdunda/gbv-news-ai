"""Exact upstream gating, append-only history, batching and failure isolation."""
from dataclasses import replace
import unittest
from unittest.mock import Mock, patch

from annotations.l2_config import L2Config, MODEL_METHOD
from annotations.l2_weak_supervision import WeakSupervisor
from annotations.schemas import AnnotationResult, DEFAULT_CONFIG
from annotations.service import run_annotation_pipeline
from scripts.run_annotations import main
from tests.test_annotation_pipeline import FakeRepository, candidate
from tests.test_annotation_rules import valid_article


class L2Repository(FakeRepository):
    def current_for_candidates(self, version_ids, methods):
        current = super().current_for_candidates(version_ids, methods)
        for version_id in version_ids:
            l1 = current.get((version_id, "L1"))
            if l1 and methods.get("L1_method_name") and l1.method_name != methods["L1_method_name"]:
                current.pop((version_id, "L1"))
                l1 = None
            if l1 and l1.label == "kenya" and "L2" in methods:
                result = next((row for row in reversed(self.results) if row.article_version_id == version_id
                               and row.layer == "L2" and row.method_name == methods["L2_method_name"]
                               and row.method_version == methods["L2"] and row.prerequisite_annotation_id == l1.id), None)
                if result:
                    current[(version_id, "L2")] = result
        return current

    def select_candidates(self, layers, methods, limit=None, article_ids=None, collection_run_id=None, only_pending=True,
                          eligible_l2_only=False):
        if "L2" not in layers:
            return super().select_candidates(layers, methods, limit, article_ids, collection_run_id, only_pending)
        current = self.current_for_candidates([c["id"] for c in self.candidates], methods)
        items = [item for item in self.candidates if (not article_ids or item["article_id"] in article_ids)
                 and (not eligible_l2_only or current.get((item["id"], "L1")) is not None
                      and current[(item["id"], "L1")].label == "kenya")
                 and (not only_pending or any((item["id"], layer) not in current for layer in layers))]
        return items if limit is None else items[:limit]


class L2PipelineTests(unittest.TestCase):
    def setUp(self):
        self.candidate = candidate()
        self.repository = L2Repository([self.candidate])
        self.objects = Mock(buckets={"processed": "processed"})
        self.objects.read_json.return_value = valid_article()
        self.predictor = Mock(method_name=MODEL_METHOD, method_version="l2-synthetic")
        self.predictor.evaluate.side_effect = lambda article: AnnotationResult(
            "L2", "gbv", MODEL_METHOD, "l2-synthetic", .9, {"gbv_probability": .9})
        self.predictor.predict_batch.side_effect = lambda articles: [self.predictor.evaluate(a) for a in articles]

    def execute(self, **kwargs):
        return run_annotation_pipeline(layers=["L2"], services=(self.repository, self.objects),
                                       l2_config=L2Config(), l2_predictor=self.predictor, **kwargs)

    def upstream(self, label="kenya", config=DEFAULT_CONFIG):
        l0 = self.repository.persist(self.candidate, None, AnnotationResult("L0", "valid", "synthetic", config.method_version("L0")))
        l1 = self.repository.persist(self.candidate, None, AnnotationResult("L1", label, "kenya_relevance_hybrid", config.method_version("L1")), l0.id)
        return l0, l1

    def test_gate_all_labels_and_missing(self):
        for label, reason in (("not_kenya", "l1_not_kenya"), ("ambiguous", "l1_ambiguous"), (None, "missing_compatible_l1")):
            self.setUp()
            if label:
                self.upstream(label)
            result = self.execute()
            self.assertEqual(result["layers"]["L2"]["skip_reasons"], {reason: 1})
            self.assertEqual(result["layers"]["L2"]["eligible"], 0)
            self.objects.read_json.assert_not_called()
            self.predictor.evaluate.assert_not_called()

    def test_only_l2_uses_exact_l1_without_rerunning_upstream(self):
        _, l1 = self.upstream()
        result = self.execute()
        self.assertEqual(result["layers"]["L2"]["processed"], 1)
        self.assertEqual([row.layer for row in self.repository.results], ["L0", "L1", "L2"])
        self.assertEqual(self.repository.results[-1].prerequisite_annotation_id, l1.id)
        self.objects.read_json.assert_called_once()

    def test_incompatible_l1_is_skipped(self):
        self.upstream(config=replace(DEFAULT_CONFIG, l1_gazetteer="v1"))
        self.assertEqual(self.execute()["skipped"], 1)
        self.predictor.evaluate.assert_not_called()

    def test_pending_force_and_upstream_replacement_preserve_history(self):
        l0, l1 = self.upstream()
        self.execute()
        old = self.repository.results[-1]
        self.assertEqual(self.execute()["requested"], 0)
        self.execute(only_pending=False)
        new_l1 = self.repository.persist(self.candidate, None, AnnotationResult("L1", "kenya", "kenya_relevance_hybrid", DEFAULT_CONFIG.method_version("L1")), l0.id)
        self.execute()
        self.assertEqual(len(self.repository.results), 6)
        self.assertIn(old, self.repository.results)
        self.assertEqual(self.repository.results[-1].prerequisite_annotation_id, new_l1.id)
        self.assertNotEqual(l1.id, new_l1.id)

    def test_weak_result_does_not_satisfy_model_pending(self):
        _, l1 = self.upstream()
        self.repository.persist(self.candidate, None, WeakSupervisor().evaluate(valid_article()), l1.id)
        self.assertEqual(self.execute()["layers"]["L2"]["processed"], 1)

    def test_bad_stored_input_fails_without_inference(self):
        for changed in (None, dict(valid_article(), article_text="changed"), dict(valid_article(), source="wrong")):
            self.setUp()
            self.upstream()
            self.objects.read_json.return_value = changed
            result = self.execute()
            self.assertEqual(result["failed"], 1)
            self.assertEqual(len(self.repository.results), 2)
            self.predictor.evaluate.assert_not_called()

    def test_batch_and_individual_failure_isolation_safe_logs(self):
        self.upstream()
        self.candidate = candidate()
        self.repository.candidates.append(self.candidate)
        self.upstream()
        self.predictor.predict_batch.side_effect = RuntimeError("PRIVATE batch text")
        self.predictor.evaluate.side_effect = [RuntimeError("PRIVATE article text"), AnnotationResult("L2", "borderline", MODEL_METHOD, "l2-synthetic")]
        with self.assertLogs("annotations.service", level="INFO") as logs:
            result = self.execute()
        self.assertEqual((result["failed"], result["success"]), (1, 1))
        self.assertEqual(result["status"], "completed_with_errors")
        self.assertNotIn("PRIVATE", str(result) + str(logs.output))
        self.predictor.predict_batch.assert_called_once()
        self.assertEqual(len(self.predictor.predict_batch.call_args.args[0]), 2)
        self.assertEqual(self.repository.results[-1].article_version_id, self.candidate["id"])

    def test_combined_layers_preserve_order_and_new_exact_dependencies(self):
        result = run_annotation_pipeline(layers=["l2", "l1", "l0"], services=(self.repository, self.objects),
                                         l2_predictor=self.predictor)
        self.assertEqual(result["success"], 1)
        self.assertEqual([row.layer for row in self.repository.results], ["L0", "L1", "L2"])
        self.assertEqual(self.repository.results[-1].prerequisite_annotation_id, self.repository.results[-2].id)

    def test_missing_model_rejects_before_cloud_access(self):
        with self.assertRaisesRegex(ValueError, "L2_MODEL_PATH"):
            run_annotation_pipeline(layers=["L2"], l2_config=L2Config())

    def test_wrong_predictor_identity_is_failed(self):
        self.upstream()
        self.predictor.evaluate.side_effect = lambda article: AnnotationResult("L2", "gbv", "wrong", "wrong")
        self.assertEqual(self.execute()["failed"], 1)
        self.assertEqual(len(self.repository.results), 2)

    def test_cli_l2_explicit_bootstrap_or_model(self):
        for mode in ("model", "weak"):
            with patch("scripts.run_annotations.run_annotation_pipeline", return_value={"failed": 0}) as runner, patch("builtins.print"):
                self.assertEqual(main(["--layer", "l2", "--l2-mode", mode, "--limit", "2"]), 0)
                self.assertEqual(runner.call_args.kwargs["l2_mode"], mode)
