"""Offline-only installed-artifact inference, reused across an annotation run."""

from functools import lru_cache
import hashlib
import json
from pathlib import Path

from annotations.l2_config import (INPUT_VERSION, LABEL_MAPPING, L1_METHOD, MODEL_METHOD,
                                   format_input, probability_label)
from annotations.schemas import AnnotationResult


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def artifact_files(path):
    """All installed files participate in identity; no silent weight replacement."""
    files = {}
    for file in sorted(Path(path).rglob("*")):
        if file.is_symlink():
            raise ValueError("L2 artifacts must not contain symlinks")
        if file.is_file() and file.name != "model_manifest.json":
            files[file.relative_to(path).as_posix()] = sha256_file(file)
    return files


@lru_cache(maxsize=8)
def read_manifest(path):
    """Artifacts are immutable for a process lifetime; restart after installing."""
    root = Path(path)
    try:
        manifest = json.loads((root / "model_manifest.json").read_text())
    except (OSError, ValueError) as exc:
        raise ValueError("L2 requires a valid local trained model_manifest.json") from exc
    if not isinstance(manifest, dict):
        raise ValueError("L2 model manifest must be a mapping")
    required = ("model_version", "base_model", "training_dataset_version", "weak_supervision_version",
                "tokenizer", "max_length", "seed", "training_parameters", "created_at", "files_sha256",
                "positive_threshold", "negative_threshold", "threshold_status")
    if any(key not in manifest or manifest[key] is None for key in required):
        raise ValueError("Incomplete L2 model reproducibility metadata")
    if (manifest.get("method_name") != MODEL_METHOD or manifest.get("label_mapping") != LABEL_MAPPING
            or manifest.get("input_version") != INPUT_VERSION or not manifest["model_version"]
            or not isinstance(manifest["model_version"], str)
            or not isinstance(manifest["max_length"], int) or manifest["max_length"] < 1):
        raise ValueError("Incompatible L2 artifact contract")
    from annotations.l2_config import L2Config
    L2Config(positive_threshold=manifest["positive_threshold"], negative_threshold=manifest["negative_threshold"])
    if (not isinstance(manifest["training_parameters"], dict)
            or not isinstance(manifest["training_parameters"].get("completed_steps"), int)
            or manifest["training_parameters"]["completed_steps"] < 1):
        raise ValueError("L2 artifact must record completed task-specific training")
    if manifest.get("training_dataset_kind") in ("reviewed_development", "mixed_effective_development"):
        required_development = ("training_record_count", "gbv_count", "not_gbv_count", "human_confirmed_count",
                                "human_corrected_count", "weak_unreviewed_count", "training_dataset_sha256",
                                "upstream_methods", "review_guideline_versions", "held_out_reference_status",
                                "label_provenance_vocabulary", "base_model_revision", "tokenizer_revision")
        if any(key not in manifest or manifest[key] is None for key in required_development):
            raise ValueError("Incomplete development model provenance")
        count_keys = ("gbv_count", "not_gbv_count", "human_confirmed_count", "human_corrected_count", "weak_unreviewed_count")
        if (any(not isinstance(manifest[key], int) or manifest[key] < 0 for key in count_keys)
                or manifest["gbv_count"] + manifest["not_gbv_count"] != manifest["training_record_count"]
                or sum(manifest[key] for key in count_keys[2:]) != manifest["training_record_count"]):
            raise ValueError("Inconsistent development model provenance counts")
        parameters = manifest["training_parameters"]
        if parameters.get("class_weighting") not in ("balanced", "none"):
            raise ValueError("Missing development class weighting strategy")
        import math
        weights = parameters.get("class_weights", {})
        if set(weights) != set(LABEL_MAPPING) or any(not math.isfinite(value) or value <= 0 for value in weights.values()):
            raise ValueError("Invalid development class weights")
    if not manifest["files_sha256"] or artifact_files(root) != manifest["files_sha256"]:
        raise ValueError("L2 model artifact checksum mismatch")
    return manifest


def model_identity(config):
    if not config.model_path:
        raise ValueError("L2_MODEL_PATH is required; install a trained L2 artifact (no weak fallback)")
    manifest = read_manifest(str(Path(config.model_path).resolve()))
    if config.model_version and manifest["model_version"] != config.model_version:
        raise ValueError("L2_MODEL_VERSION does not match installed artifact")
    semantics = {"manifest": manifest, "positive_threshold": config.positive_threshold,
                 "negative_threshold": config.negative_threshold, "inference_version": "l2-inference-v1"}
    digest = hashlib.sha256(json.dumps(semantics, sort_keys=True).encode()).hexdigest()
    return manifest, "l2-" + digest[:24]


def current_l2_methods(config=None):
    """Monitor can report zero model coverage before any model is installed."""
    from annotations.l2_config import L2Config
    config = config or L2Config.from_env()
    version = model_identity(config)[1] if config.model_path else "l2-model-unconfigured"
    return {"L2": version, "L2_method_name": MODEL_METHOD, "L1_method_name": L1_METHOD}


def select_device(torch, requested="auto"):
    if requested != "auto":
        return requested
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def maximum_length(tokenizer, model, requested):
    limits = [requested]
    token_limit = getattr(tokenizer, "model_max_length", None)
    if isinstance(token_limit, int) and 0 < token_limit < 1_000_000:
        limits.append(token_limit)
    # XLM-R position embeddings reserve indices for the padding offset.
    positions = getattr(model.config, "max_position_embeddings", None)
    padding = getattr(model.config, "pad_token_id", 1)
    if isinstance(positions, int):
        limits.append(positions - (padding if isinstance(padding, int) else 1) - 1)
    result = min(limits)
    if result < 1:
        raise ValueError("Invalid tokenizer/model maximum length")
    return result


class TransformerPredictor:
    method_name = MODEL_METHOD

    def __init__(self, config, runtime=None):
        self.config = config
        self.manifest, self.method_version = model_identity(config)
        if runtime is None:
            try:
                import torch
                from transformers import AutoModelForSequenceClassification, AutoTokenizer
            except ImportError as exc:
                raise ValueError("Install requirements-l2.txt for L2 Transformer inference") from exc
            runtime = torch, AutoTokenizer, AutoModelForSequenceClassification
        self.torch, tokenizer_factory, model_factory = runtime
        self.tokenizer = tokenizer_factory.from_pretrained(config.model_path, local_files_only=True,
                                                          trust_remote_code=False)
        self.tokenizer.truncation_side = "right"
        self.model = model_factory.from_pretrained(config.model_path, local_files_only=True,
                                                  trust_remote_code=False, use_safetensors=True)
        if (self.model.config.num_labels != 2 or
                {str(key): value for key, value in self.model.config.id2label.items()}
                != {"0": "not_gbv", "1": "gbv"}):
            raise ValueError("L2 requires a trained binary GBV head with explicit label order")
        self.device = select_device(self.torch, config.device)
        self.model.to(self.device)
        self.model.eval()
        self.max_length = maximum_length(self.tokenizer, self.model, self.manifest["max_length"])

    def evaluate(self, article):
        return self.predict_batch([article])[0]

    def predict_batch(self, articles):
        results = []
        for offset in range(0, len(articles), self.config.batch_size):
            batch = articles[offset:offset + self.config.batch_size]
            encoded = self.tokenizer([format_input(article) for article in batch], padding=True,
                                     truncation=True, max_length=self.max_length, return_tensors="pt")
            encoded = {key: value.to(self.device) for key, value in encoded.items()}
            with self.torch.inference_mode():
                logits = self.model(**encoded).logits
                if len(logits.shape) != 2 or logits.shape[0] != len(batch) or logits.shape[1] != 2:
                    raise ValueError("Invalid L2 model output shape")
                probabilities = self.torch.softmax(logits, dim=-1)[:, LABEL_MAPPING["gbv"]].cpu().tolist()
            for probability in probabilities:
                label = probability_label(probability, self.config)
                evidence = {"gbv_probability": probability, "confidence_kind": "uncalibrated_softmax_probability",
                            "positive_threshold": self.config.positive_threshold,
                            "negative_threshold": self.config.negative_threshold,
                            "threshold_status": "UNVALIDATED ENGINEERING THRESHOLDS",
                            "model_version": self.manifest["model_version"],
                            "base_model": self.manifest["base_model"], "tokenizer": self.manifest["tokenizer"],
                            "training_dataset_version": self.manifest["training_dataset_version"],
                            "weak_supervision_version": self.manifest["weak_supervision_version"],
                            "artifact_identity": self.method_version, "input_version": INPUT_VERSION,
                            "max_length": self.max_length, "truncation": "deterministic_head"}
                results.append(AnnotationResult("L2", label, self.method_name, self.method_version,
                                                confidence=probability, evidence=evidence,
                                                reason_codes=["model_" + label, "uncalibrated_prediction_not_reference"]))
        return results


@lru_cache(maxsize=4)
def get_predictor(mode, config):
    if mode == "weak":
        from annotations.l2_weak_supervision import WeakSupervisor
        return WeakSupervisor()
    if mode != "model":
        raise ValueError("Unknown L2 mode")
    return TransformerPredictor(config)
