"""Private development export contracts and explicit binary Transformer training."""

from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import random
import subprocess
from time import perf_counter
import logging

from annotations.l2 import artifact_files, maximum_length, select_device, sha256_file
from annotations.l2_config import BASE_MODEL, INPUT_VERSION, LABEL_MAPPING, L1_METHOD, MODEL_METHOD, L2Config, format_input
from annotations.l2_weak_supervision import WEAK_METHOD, weak_method_version
from annotations.schemas import DEFAULT_CONFIG
from annotations.service import load_verified_article

ROOT = Path(__file__).resolve().parents[1]


def private_output(path):
    path = Path(path).resolve()
    if not any(path.is_relative_to(root) and path != root for root in
               (ROOT / "data", ROOT / "models" / "artifacts")):
        raise ValueError("Keep private L2 outputs under data/ or models/artifacts/")
    return path


def bootstrap_methods(config=DEFAULT_CONFIG):
    return {"L0": config.method_version("L0"), "L1": config.method_version("L1"),
            "L1_method_name": L1_METHOD,
            "L2": weak_method_version(), "L2_method_name": WEAK_METHOD}


def build_bootstrap(repository, objects, output_dir, limit=None, config=DEFAULT_CONFIG):
    """Export existing exact-compatible binary weak labels, never create annotations."""
    output = private_output(output_dir)
    methods = bootstrap_methods(config)
    from annotations.validation_batches import EMPTY_MEMBERSHIP, excluded
    protected = repository.protected_membership() if hasattr(repository, "protected_membership") else EMPTY_MEMBERSHIP
    candidates = repository.select_candidates(["L2"], methods, limit=limit, only_pending=False, eligible_l2_only=True)
    current = repository.current_for_candidates([item["id"] for item in candidates], methods)
    records, skipped, seen_hashes = [], Counter(), set()
    for candidate in sorted(candidates, key=lambda item: str(item["id"])):
        if excluded(candidate, protected):
            skipped["held_out_reference"] += 1
            continue

        version_id = candidate["id"]
        l0, l1, weak = (current.get((version_id, layer)) for layer in ("L0", "L1", "L2"))
        if (l0 is None or l0.label != "valid" or l1 is None or l1.label != "kenya"
                or l1.prerequisite_annotation_id != l0.id):
            skipped["not_current_l1_kenya"] += 1
            continue
        if (weak is None or weak.prerequisite_annotation_id != l1.id
                or weak.method_name != WEAK_METHOD or weak.method_version != methods["L2"]):
            skipped["missing_compatible_weak_label"] += 1
            continue
        if weak.label not in LABEL_MAPPING:
            skipped["borderline"] += 1
            continue
        article = load_verified_article(candidate, objects)
        if candidate["content_hash"] in seen_hashes:
            skipped["duplicate_body_hash"] += 1
            continue
        seen_hashes.add(candidate["content_hash"])
        records.append({"article_id": str(candidate["article_id"]), "article_version_id": str(version_id),
                        "prerequisite_l1_annotation_id": str(l1.id), "l1_method_version": l1.method_version,
                        "l1_method_name": l1.method_name,
                        "weak_annotation_id": str(weak.id), "weak_method_version": weak.method_version,
                        "weak_method_name": weak.method_name, "label_source": "weak_original",
                        "human_validation_id": None, "human_guideline_version": None,
                        "dataset_membership": "development_train", "input_version": INPUT_VERSION,
                        "weak_rule_version": weak.evidence["rule_version"], "source": article["source"],
                        "language": article.get("language"), "content_hash": candidate["content_hash"],
                        "label": weak.label, "label_id": LABEL_MAPPING[weak.label], "input": format_input(article)})
    payload = "".join(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n" for record in records)
    digest = hashlib.sha256(payload.encode()).hexdigest()
    manifest = {"dataset_version": "l2-bootstrap-" + digest[:24], "kind": "weak_bootstrap_development",
                "labels_are_gold": False, "input_version": INPUT_VERSION, "label_mapping": LABEL_MAPPING,
                "label_policy": "weak-only", "label_provenance_vocabulary": ["weak_original"],
                "weak_supervision_version": methods["L2"], "upstream_methods": methods,
                "records_sha256": digest, "record_count": len(records),
                "label_counts": dict(sorted(Counter(record["label"] for record in records).items())),
                "skipped": dict(sorted(skipped.items())), "selection_limit": limit,
                "split_status": "development_only_no_reference_or_heldout_test"}
    output.mkdir(parents=True, exist_ok=False)
    (output / "bootstrap.jsonl").write_text(payload, encoding="utf-8")
    (output / "dataset_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def load_bootstrap(dataset_dir, expected_version=None):
    path = Path(dataset_dir)
    manifest = json.loads((path / "dataset_manifest.json").read_text())
    if (manifest.get("kind") != "weak_bootstrap_development" or manifest.get("labels_are_gold") is not False
            or manifest.get("input_version") != INPUT_VERSION or manifest.get("label_mapping") != LABEL_MAPPING
            or manifest.get("split_status") != "development_only_no_reference_or_heldout_test"):
        raise ValueError("Training requires a weak bootstrap development manifest, not reference/test data")
    if expected_version and manifest["dataset_version"] != expected_version:
        raise ValueError("Training dataset version mismatch")
    if sha256_file(path / "bootstrap.jsonl") != manifest["records_sha256"]:
        raise ValueError("Bootstrap dataset checksum mismatch")
    records = [json.loads(line) for line in (path / "bootstrap.jsonl").read_text().splitlines() if line]
    if len(records) != manifest["record_count"] or not records:
        raise ValueError("Empty or inconsistent bootstrap dataset")
    for record in records:
        if (record.get("label") not in LABEL_MAPPING or record.get("label_id") != LABEL_MAPPING[record["label"]]
                or record.get("weak_method_version") != manifest["weak_supervision_version"]
                or not isinstance(record.get("input"), str)
                or any(not record.get(key) for key in ("article_id", "article_version_id",
                                                       "prerequisite_l1_annotation_id", "weak_annotation_id"))):
            raise ValueError("Invalid bootstrap training row/lineage")
    if {record["label"] for record in records} != set(LABEL_MAPPING):
        raise ValueError("Binary bootstrap training requires examples from both classes")
    return records, manifest


def load_training_data(dataset_dir, expected_version=None):
    """Preserve weak exports while explicitly accepting reviewed development kinds."""
    manifest = json.loads((Path(dataset_dir) / "dataset_manifest.json").read_text())
    if manifest.get("kind") == "weak_bootstrap_development":
        return load_bootstrap(dataset_dir, expected_version)
    from annotations.l2_datasets import load_development
    return load_development(dataset_dir, expected_version)


def class_weights(records, strategy):
    if strategy not in ("balanced", "none"):
        raise ValueError("Unknown class weighting strategy")
    counts = Counter(row["label"] for row in records)
    if any(not counts[label] for label in LABEL_MAPPING):
        raise ValueError("Class weighting requires both classes")
    return {label: len(records) / (len(LABEL_MAPPING) * counts[label]) if strategy == "balanced" else 1.0
            for label in LABEL_MAPPING}


def training_provenance(dataset, records):
    """Aggregate dataset lineage for artifacts; never export reviewer identities."""
    from annotations.l2_datasets import LABEL_SOURCES, NO_REFERENCE, NO_VALIDATION
    counts = Counter(row["label"] for row in records)
    origins = Counter(row.get("label_source", "weak_original") for row in records)
    skipped = dataset.get("skipped", {})
    return {"training_dataset_name": dataset.get("dataset_name", "historical-weak-bootstrap-development"),
            "training_dataset_kind": dataset["kind"], "label_policy": dataset.get("label_policy", "weak-only"),
            "training_record_count": len(records), "gbv_count": counts["gbv"], "not_gbv_count": counts["not_gbv"],
            "human_confirmed_count": origins["human_confirmed"], "human_corrected_count": origins["human_corrected"],
            "weak_unreviewed_count": origins["weak_unreviewed"],
            "label_provenance_vocabulary": list(LABEL_SOURCES) + (["weak_original"] if origins["weak_original"] else []),
            "weak_original_count": origins["weak_original"],
            "excluded_borderline_count": skipped.get("borderline", 0), "excluded_unresolved_count": skipped.get("unresolved", 0),
            "excluded_duplicate_count": sum(skipped.get(key, 0) for key in ("duplicate_body_hash", "duplicate_article_version", "duplicate_conflicting_labels")),
            "upstream_methods": dataset.get("upstream_methods", {}),
            "review_guideline_versions": dataset.get("review_guideline_versions", []),
            "held_out_reference_status": dataset.get("held_out_reference_status", NO_REFERENCE),
            "reference_manifest_sha256": dataset.get("reference_manifest_sha256"),
            "validation_status": dataset.get("validation_status", NO_VALIDATION)}


def train_classifier(dataset_dir, output_dir, model_version, base_model=BASE_MODEL, revision=None,
                     epochs=1, batch_size=4, learning_rate=2e-5, max_length=512, seed=42,
                     max_steps=None, device="auto", dataset_version=None, local_files_only=False,
                     l2_config=None, class_weighting="none", weight_decay=0.01, cache_dir=None):
    """Explicit development training. Report training loss, never reference accuracy/F1."""
    import math
    if (epochs < 1 or batch_size < 1 or max_length < 1 or not math.isfinite(learning_rate)
            or learning_rate <= 0 or max_steps is not None and max_steps < 1
            or not model_version or device not in ("auto", "cpu", "cuda", "mps")
            or class_weighting not in ("balanced", "none") or not math.isfinite(weight_decay) or weight_decay < 0):
        raise ValueError("Invalid training parameters")
    output = private_output(output_dir)
    if output.exists():
        raise ValueError("Use a new output directory; trained artifacts are immutable")
    records, dataset = load_training_data(dataset_dir, dataset_version)
    weights = class_weights(records, class_weighting)
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True, warn_only=True)
    tokenizer = AutoTokenizer.from_pretrained(base_model, revision=revision, local_files_only=local_files_only,
                                             trust_remote_code=False, cache_dir=cache_dir)
    model = AutoModelForSequenceClassification.from_pretrained(
        base_model, revision=revision, local_files_only=local_files_only, trust_remote_code=False,
        num_labels=2, id2label={index: label for label, index in LABEL_MAPPING.items()},
        label2id=LABEL_MAPPING, use_safetensors=True, cache_dir=cache_dir)
    selected_device = select_device(torch, device)
    model.to(selected_device)
    length = maximum_length(tokenizer, model, max_length)
    tokenizer.truncation_side = "right"
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)
    weight_tensor = torch.tensor([weights[label] for label in LABEL_MAPPING], dtype=torch.float32, device=selected_device)
    rng = random.Random(seed)
    losses, steps, epoch_losses = [], 0, []
    started = perf_counter()
    model.train()
    for epoch in range(epochs):
        epoch_values = []
        indices = list(range(len(records)))
        rng.shuffle(indices)
        for offset in range(0, len(indices), batch_size):
            batch = [records[index] for index in indices[offset:offset + batch_size]]
            encoded = tokenizer([row["input"] for row in batch], padding=True, truncation=True,
                                max_length=length, return_tensors="pt")
            encoded = {key: value.to(selected_device) for key, value in encoded.items()}
            labels = torch.tensor([row["label_id"] for row in batch], dtype=torch.long, device=selected_device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(**encoded).logits
            # Mean over examples (not sum of batch weights) preserves the balanced
            # population objective even for singleton/one-class minibatches.
            per_example = torch.nn.functional.cross_entropy(logits, labels, reduction="none")
            loss = (per_example * weight_tensor[labels]).mean()
            if not torch.isfinite(loss).item():
                raise ValueError("Nonfinite development training loss")
            loss.backward()
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
            epoch_values.append(losses[-1])
            steps += 1
            if steps == 1 or steps % 10 == 0:
                logging.getLogger(__name__).info("l2_training epoch=%s step=%s loss=%.6f elapsed_s=%.1f",
                                                epoch + 1, steps, losses[-1], perf_counter() - started)
            if max_steps and steps >= max_steps:
                break
        epoch_losses.append(sum(epoch_values) / len(epoch_values))
        if max_steps and steps >= max_steps:
            break
    if selected_device == "mps":
        torch.mps.synchronize()
    elif selected_device == "cuda":
        torch.cuda.synchronize()
    duration = perf_counter() - started
    model.eval()
    output.mkdir(parents=True, exist_ok=False)
    model.save_pretrained(output, safe_serialization=True)
    tokenizer.save_pretrained(output)
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True))
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = None, None
    config = l2_config or L2Config()
    manifest = {"model_version": model_version, "method_name": MODEL_METHOD, "base_model": base_model,
                "base_model_revision": getattr(model.config, "_commit_hash", None) or revision,
                "created_at": datetime.now(timezone.utc).isoformat(), "training_dataset_version": dataset["dataset_version"],
                "training_dataset_sha256": dataset["records_sha256"],
                "training_dataset_manifest_sha256": sha256_file(Path(dataset_dir) / "dataset_manifest.json"),
                "weak_supervision_version": dataset["weak_supervision_version"], "label_mapping": LABEL_MAPPING,
                "training_parameters": {"epochs": epochs, "batch_size": batch_size, "learning_rate": learning_rate,
                                        "max_steps": max_steps, "device": selected_device, "completed_steps": steps,
                                        "weight_decay": weight_decay, "class_weighting": class_weighting,
                                        "class_weights": weights, "loss_reduction": "weighted_sum_divided_by_batch_examples",
                                        "effective_max_length": length, "seed": seed},
                "positive_threshold": config.positive_threshold, "negative_threshold": config.negative_threshold,
                "threshold_status": "UNVALIDATED ENGINEERING THRESHOLDS", "tokenizer": base_model,
                "confidence_kind": "uncalibrated_softmax_probability",
                "tokenizer_revision": tokenizer.init_kwargs.get("_commit_hash") or revision,
                "max_length": length, "seed": seed, "input_version": INPUT_VERSION,
                "code_commit": commit, "code_worktree_dirty": dirty,
                "determinism": "seeded_order_and_torch_warn_only_algorithms_backend_variation_possible",
                "libraries": {name: importlib.metadata.version(name) for name in ("torch", "transformers", "safetensors")},
                "device_availability": {"cuda": torch.cuda.is_available(), "mps": torch.backends.mps.is_available()},
                "training_duration_seconds": duration,
                "development_diagnostics": {"kind": "development_training_loss_not_research_evaluation",
                                            "mean_training_loss": sum(losses) / len(losses), "epoch_mean_losses": epoch_losses,
                                            "independent_validation_metrics": None},
                **training_provenance(dataset, records),
                "files_sha256": artifact_files(output)}
    (output / "model_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest
