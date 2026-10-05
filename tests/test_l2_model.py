"""Fake tensor/runtime inference tests: no network, model download or ML dependency."""
from contextlib import nullcontext
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from annotations.l2 import (TransformerPredictor, artifact_files, get_predictor, maximum_length,
                            model_identity, read_manifest, select_device)
from annotations.l2_config import INPUT_VERSION, LABEL_MAPPING, MODEL_METHOD, L2Config, format_input, probability_label


def synthetic_artifact(path):
    path = Path(path)
    (path / "model.safetensors").write_bytes(b"synthetic unit-test weights, not a usable model")
    manifest = {"model_version": "synthetic-v1", "method_name": MODEL_METHOD, "base_model": "synthetic-local",
                "training_dataset_version": "l2-bootstrap-synthetic", "weak_supervision_version": "l2-ws-synthetic",
                "label_mapping": LABEL_MAPPING, "created_at": "2026-10-05T00:00:00Z", "tokenizer": "synthetic-local",
                "max_length": 1000, "seed": 42, "training_parameters": {"completed_steps": 1},
                "positive_threshold": .8, "negative_threshold": .2,
                "threshold_status": "UNVALIDATED ENGINEERING THRESHOLDS",
                "input_version": INPUT_VERSION, "files_sha256": artifact_files(path)}
    (path / "model_manifest.json").write_text(json.dumps(manifest))
    return manifest


class Inputs:
    def __init__(self, texts):
        self.texts = texts
    def to(self, device):
        return self


class Probabilities:
    def __init__(self, rows):
        self.rows = rows
    def __getitem__(self, key):
        assert key == (slice(None), 1)
        return self
    def cpu(self):
        return self
    def tolist(self):
        return self.rows


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        read_manifest.cache_clear()
        get_predictor.cache_clear()
        self.manifest = synthetic_artifact(self.directory.name)
        self.config = L2Config(model_path=self.directory.name, batch_size=2)
        self.tokenizer = Mock(model_max_length=512)
        self.tokenizer.side_effect = lambda texts, **kw: {"input_ids": Inputs(texts)}
        self.model = Mock()
        self.model.config = SimpleNamespace(num_labels=2, id2label={0: "not_gbv", 1: "gbv"}, max_position_embeddings=514, pad_token_id=1)
        self.model.side_effect = lambda **kw: SimpleNamespace(logits=SimpleNamespace(
            shape=(len(kw["input_ids"].texts), 2), texts=kw["input_ids"].texts))
        self.torch = Mock()
        self.torch.cuda.is_available.return_value = False
        self.torch.backends.mps.is_available.return_value = False
        self.torch.inference_mode.side_effect = nullcontext
        self.torch.softmax.side_effect = lambda logits, **kw: Probabilities([
            .9 if "positive" in text else .1 if "negative" in text else .5 for text in logits.texts])
        self.tokenizer_factory = Mock()
        self.tokenizer_factory.from_pretrained.return_value = self.tokenizer
        self.model_factory = Mock()
        self.model_factory.from_pretrained.return_value = self.model

    def predictor(self):
        return TransformerPredictor(self.config, runtime=(self.torch, self.tokenizer_factory, self.model_factory))

    def test_batch_probability_mapping_and_reused_offline_loader(self):
        predictor = self.predictor()
        results = predictor.predict_batch([{"title": word, "article_text": "Synthetic."} for word in ("positive", "negative", "neutral")])
        self.assertEqual([r.label for r in results], ["gbv", "not_gbv", "borderline"])
        self.assertEqual([r.confidence for r in results], [.9, .1, .5])
        self.assertEqual(self.model.call_count, 2)
        self.model.eval.assert_called_once()
        for factory in (self.tokenizer_factory, self.model_factory):
            factory.from_pretrained.assert_called_once()
            self.assertTrue(factory.from_pretrained.call_args.kwargs["local_files_only"])
            self.assertFalse(factory.from_pretrained.call_args.kwargs["trust_remote_code"])
        self.assertEqual(self.tokenizer.call_args.kwargs["max_length"], 512)
        self.assertTrue(self.tokenizer.call_args.kwargs["truncation"])
        self.assertEqual(results[0].evidence["confidence_kind"], "uncalibrated_softmax_probability")
        self.assertEqual(self.tokenizer.truncation_side, "right")

    def test_process_predictor_cache_loads_once(self):
        with patch("annotations.l2.TransformerPredictor") as factory:
            self.assertIs(get_predictor("model", self.config), get_predictor("model", self.config))
            factory.assert_called_once()

    def test_threshold_boundaries_and_invalid_probabilities(self):
        self.assertEqual(probability_label(.8, self.config), "gbv")
        self.assertEqual(probability_label(.2, self.config), "not_gbv")
        self.assertEqual(probability_label(.3, self.config), "borderline")
        for value in (float("nan"), float("inf"), -1, 2):
            with self.assertRaises(ValueError):
                probability_label(value, self.config)
        for kwargs in ({"positive_threshold": .2, "negative_threshold": .2}, {"positive_threshold": float("nan")}):
            with self.assertRaises(ValueError):
                L2Config(**kwargs)

    def test_threshold_and_artifact_semantics_change_identity(self):
        identity = model_identity(self.config)[1]
        self.assertNotEqual(identity, model_identity(replace(self.config, positive_threshold=.85))[1])
        manifest = dict(self.manifest, training_dataset_version="l2-bootstrap-changed")
        (Path(self.directory.name) / "model_manifest.json").write_text(json.dumps(manifest))
        read_manifest.cache_clear()
        self.assertNotEqual(identity, model_identity(self.config)[1])

    def test_missing_manifest_corrupt_weights_and_version_mismatch(self):
        with self.assertRaisesRegex(ValueError, "L2_MODEL_PATH"):
            model_identity(L2Config())
        with self.assertRaisesRegex(ValueError, "L2_MODEL_VERSION"):
            model_identity(replace(self.config, model_version="wrong"))
        (Path(self.directory.name) / "model.safetensors").write_bytes(b"replaced")
        read_manifest.cache_clear()
        with self.assertRaisesRegex(ValueError, "checksum"):
            model_identity(self.config)

    def test_manifest_rejects_untrained_and_malformed_metadata(self):
        for manifest in ([], dict(self.manifest, training_parameters={"completed_steps": 0}),
                         dict(self.manifest, training_parameters=[]),
                         dict(self.manifest, positive_threshold="invalid")):
            (Path(self.directory.name) / "model_manifest.json").write_text(json.dumps(manifest))
            read_manifest.cache_clear()
            with self.assertRaises(ValueError):
                model_identity(self.config)

    def test_binary_head_order_and_inference_failure(self):
        self.model.config.id2label = {0: "gbv", 1: "not_gbv"}
        with self.assertRaisesRegex(ValueError, "binary GBV head"):
            self.predictor()
        self.model.config.id2label = {0: "not_gbv", 1: "gbv"}
        predictor = self.predictor()
        self.model.side_effect = RuntimeError("synthetic backend failure")
        with self.assertRaises(RuntimeError):
            predictor.evaluate({"title": "Synthetic", "article_text": "Synthetic"})

    def test_devices_and_maximum_input_length(self):
        self.assertEqual(select_device(self.torch), "cpu")
        self.torch.backends.mps.is_available.return_value = True
        self.assertEqual(select_device(self.torch), "mps")
        self.torch.cuda.is_available.return_value = True
        self.assertEqual(select_device(self.torch), "cuda")
        self.assertEqual(select_device(self.torch, "cpu"), "cpu")
        self.tokenizer.model_max_length = 10**30
        self.assertEqual(maximum_length(self.tokenizer, self.model, 1000), 512)

    def test_input_format_and_no_network_fallback(self):
        self.assertEqual(format_input({"title": " Heading ", "article_text": " Body "}), "TITLE:\nHeading\n\nARTICLE:\nBody")
        with self.assertRaises(ValueError):
            format_input({"title": "Heading"})
        with self.assertRaises(ValueError):
            get_predictor("unknown", self.config)

    @unittest.skipUnless(os.getenv("GBV_L2_INTEGRATION_MODEL"), "Optional local trained model is not configured")
    def test_optional_installed_local_model(self):
        predictor = TransformerPredictor(L2Config(model_path=os.environ["GBV_L2_INTEGRATION_MODEL"], device="cpu"))
        result = predictor.evaluate({"title": "Synthetic school news", "article_text": "A synthetic school opened."})
        self.assertIn(result.label, ("gbv", "not_gbv", "borderline"))
