"""Deterministic private development export and training-data integrity checks."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from annotations.l2_config import LABEL_MAPPING
from annotations.l2_training import ROOT, build_bootstrap, load_bootstrap, private_output, train_classifier
from annotations.l2_weak_supervision import WeakSupervisor
from annotations.schemas import AnnotationResult, DEFAULT_CONFIG
from tests.test_l2_pipeline import L2Repository
from tests.test_annotation_pipeline import candidate
from tests.test_annotation_rules import valid_article


class TrainingDataTests(unittest.TestCase):
    def setUp(self):
        (ROOT / "data").mkdir(exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=ROOT / "data")
        self.addCleanup(self.directory.cleanup)
        self.repository = L2Repository([])
        self.objects = Mock(buckets={"processed": "processed"})
        self.objects.read_json.return_value = valid_article()
        self.weak = WeakSupervisor()

    def add(self, label="gbv", l1_label="kenya", l1_config=DEFAULT_CONFIG, prerequisite=None, same_hash=False):
        item = candidate()
        # Different synthetic hashes are supplied with matching records below.
        record = valid_article()
        if not same_hash:
            import hashlib
            record["article_text"] += " " + str(len(self.repository.candidates))
            item["content_hash"] = record["content_hash"] = hashlib.sha256(record["article_text"].encode()).hexdigest()
        item["processed_object_uri"] = "gs://processed/" + str(item["id"]) + ".json"
        self.repository.candidates.append(item)
        if not hasattr(self, "records"):
            self.records = {}
        self.records[str(item["id"]) + ".json"] = record
        self.objects.read_json.side_effect = lambda role, key, generation=None: self.records[key]
        l0 = self.repository.persist(item, None, AnnotationResult("L0", "valid", "synthetic", DEFAULT_CONFIG.method_version("L0")))
        l1 = self.repository.persist(item, None, AnnotationResult("L1", l1_label, "kenya_relevance_hybrid", l1_config.method_version("L1")), l0.id)
        weak = replace(self.weak.evaluate(record), label=label)
        self.repository.persist(item, None, weak, prerequisite or l1.id)
        return item, l1

    def output(self, name):
        return Path(self.directory.name) / name

    def test_deterministic_manifest_exact_lineage_and_binary_only(self):
        included, prerequisite = self.add("gbv")
        self.add("not_gbv")
        self.add("borderline")
        self.add("gbv", "ambiguous")
        self.add("gbv", l1_config=replace(DEFAULT_CONFIG, l1_gazetteer="v1"))
        first = build_bootstrap(self.repository, self.objects, self.output("one"))
        second = build_bootstrap(self.repository, self.objects, self.output("two"))
        self.assertEqual(first, second)
        self.assertEqual(first["record_count"], 2)
        self.assertEqual(first["skipped"]["borderline"], 1)
        records, manifest = load_bootstrap(self.output("one"), first["dataset_version"])
        self.assertFalse(manifest["labels_are_gold"])
        row = next(record for record in records if record["article_version_id"] == str(included["id"]))
        self.assertEqual(row["prerequisite_l1_annotation_id"], str(prerequisite.id))
        self.assertEqual(row["label_id"], LABEL_MAPPING["gbv"])
        self.assertNotIn("canonical_url", row)
        self.assertNotIn("author", row)
        self.assertIn("TITLE:", row["input"])
        with self.assertRaises(FileExistsError):
            build_bootstrap(self.repository, self.objects, self.output("one"))

    def test_wrong_weak_prerequisite_excluded_and_duplicate_body_hash_deduped(self):
        self.add("gbv", same_hash=True)
        self.add("gbv", same_hash=True)
        self.add("not_gbv")
        from uuid import uuid4
        self.add("gbv", prerequisite=uuid4())
        manifest = build_bootstrap(self.repository, self.objects, self.output("unique"))
        self.assertEqual(manifest["record_count"], 2)
        self.assertEqual(manifest["skipped"]["duplicate_body_hash"], 1)
        self.assertEqual(manifest["skipped"]["missing_compatible_weak_label"], 1)

    def test_corrupt_export_or_reference_data_cannot_train(self):
        self.add("gbv")
        self.add("not_gbv")
        build_bootstrap(self.repository, self.objects, self.output("export"))
        path = self.output("export")
        with self.assertRaisesRegex(ValueError, "version mismatch"):
            load_bootstrap(path, "wrong")
        data = path / "bootstrap.jsonl"
        data.write_text(data.read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "checksum"):
            load_bootstrap(path)
        manifest_path = path / "dataset_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["kind"] = "human_reference_test"
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "development manifest"):
            load_bootstrap(path)

    def test_one_class_empty_invalid_parameters_and_private_output(self):
        self.add("gbv")
        build_bootstrap(self.repository, self.objects, self.output("single"))
        with self.assertRaisesRegex(ValueError, "both classes"):
            load_bootstrap(self.output("single"))
        with self.assertRaises(ValueError):
            private_output(ROOT / "tests" / "leak")
        with self.assertRaisesRegex(ValueError, "Invalid training parameters"):
            train_classifier(self.output("single"), self.output("model"), "synthetic", epochs=0)

    def test_corrupt_stored_article_is_not_exported(self):
        self.add("gbv")
        self.objects.read_json.side_effect = None
        self.objects.read_json.return_value = dict(valid_article(), article_text="corrupt")
        with self.assertRaises(ValueError):
            build_bootstrap(self.repository, self.objects, self.output("corrupt"))
        self.assertFalse(self.output("corrupt").exists())
