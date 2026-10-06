"""Private reviewed/mixed development data, separate from historical weak exports."""

from collections import Counter, defaultdict
import hashlib
import json
import logging
from pathlib import Path
from uuid import UUID

from annotations.l2 import sha256_file
from annotations.l2_config import INPUT_VERSION, LABEL_MAPPING, format_input
from annotations.schemas import DEFAULT_CONFIG
from annotations.service import load_verified_article

POLICIES = {"reviewed-only": "reviewed_development", "mixed-effective": "mixed_effective_development"}
LABEL_SOURCES = ("human_confirmed", "human_corrected", "weak_unreviewed")
NO_REFERENCE = "NO FINAL HELD-OUT HUMAN REFERENCE SET IS CURRENTLY FROZEN"
NO_VALIDATION = "NO RELIABLE INDEPENDENT DEVELOPMENT VALIDATION METRICS DUE TO LIMITED POSITIVE CLASS SUPPORT"


def reference_membership(path=None):
    """Accept explicit frozen membership only; never designate a reference split."""
    if path is None:
        return {"article_ids": set(), "article_version_ids": set(), "content_hashes": set()}, NO_REFERENCE, None
    data = json.loads(Path(path).read_text())
    if data.get("kind") != "human_reference_test" or data.get("frozen") is not True:
        raise ValueError("Reference exclusions require a frozen human_reference_test membership manifest")
    membership = {key: set(data.get(key, [])) for key in ("article_ids", "article_version_ids", "content_hashes")}
    if not any(membership.values()):
        raise ValueError("Empty reference membership")
    for key in ("article_ids", "article_version_ids"):
        membership[key] = {str(UUID(value)) for value in membership[key]}
    if any(len(value) != 64 or any(c not in "0123456789abcdef" for c in value)
           for value in membership["content_hashes"]):
        raise ValueError("Invalid reference content hash")
    return membership, "frozen_reference_membership_excluded", sha256_file(path)


def resolve_label(weak, review, policy):
    """Unresolved human decisions block weak fallback under every reviewed policy."""
    if policy not in POLICIES:
        raise ValueError("Unknown development label policy")
    if review is None:
        if policy == "reviewed-only":
            return None, None, "unreviewed"
        return (weak.label, "weak_unreviewed", None) if weak.label in LABEL_MAPPING else (None, None, "borderline")
    for field, expected in (("automated_annotation_id", weak.id), ("article_id", weak.article_id),
                            ("article_version_id", weak.article_version_id), ("layer", "L2"),
                            ("machine_label", weak.label)):
        if review[field] != expected:
            raise ValueError("Human review lineage does not match current machine result")
    decision = review["review_decision"]
    if decision in ("unable_to_determine", "needs_adjudication"):
        return None, None, "unresolved"
    if decision not in ("confirmed", "corrected"):
        raise ValueError("Unsupported human decision")
    label = weak.label if decision == "confirmed" else review["human_label"]
    if label == "borderline":
        return None, None, "borderline"
    if label not in LABEL_MAPPING:
        raise ValueError("Invalid resolved human label")
    return label, "human_" + decision, None


def build_development(repository, reviews, objects, output_dir, label_policy, limit=None,
                      config=DEFAULT_CONFIG, reference_manifest=None):
    from annotations.l2_training import bootstrap_methods, private_output
    output = private_output(output_dir)
    if output.exists():
        raise FileExistsError("Use a new private dataset directory")
    if label_policy not in POLICIES:
        raise ValueError("Unknown development label policy")
    methods = bootstrap_methods(config)
    membership, reference_status, reference_hash = reference_membership(reference_manifest)
    if hasattr(repository, "protected_membership"):
        automatic = repository.protected_membership()
        membership = {key: membership[key] | automatic[key] for key in membership}
        if any(automatic.values()):
            reference_status = "application_protected_and_optional_external_membership_excluded"

    candidates = repository.select_candidates(["L2"], methods, limit=limit, only_pending=False, eligible_l2_only=True)
    current = repository.current_for_candidates([item["id"] for item in candidates], methods)
    latest = reviews.latest_for_annotations([row.id for (version, layer), row in current.items() if layer == "L2"])
    skipped, exclusions, resolved, seen_versions = Counter(), [], [], set()

    def exclude(item, reason, retained_version=None):
        skipped[reason] += 1
        exclusions.append({"article_id": str(item["article_id"]), "article_version_id": str(item["id"]),
                           "reason": reason, "retained_article_version_id": retained_version})

    # Also protect identical bodies of reference members even if the explicit
    # membership manifest supplied only article/version IDs.
    reference_hashes = set(membership["content_hashes"])
    if membership["article_ids"] or membership["article_version_ids"]:
        if hasattr(repository, "reference_content_hashes"):
            reference_hashes.update(repository.reference_content_hashes(
                membership["article_ids"], membership["article_version_ids"]))
        else:
            known_articles = {str(item["article_id"]) for item in candidates}
            known_versions = {str(item["id"]) for item in candidates}
            if not (membership["article_ids"] <= known_articles and membership["article_version_ids"] <= known_versions):
                raise ValueError("Cannot protect out-of-cohort reference bodies without repository hash lookup")
    for item in candidates:
        if str(item["article_id"]) in membership["article_ids"] or str(item["id"]) in membership["article_version_ids"]:
            reference_hashes.add(item["content_hash"])
    for item in sorted(candidates, key=lambda row: str(row["id"])):
        version = item["id"]
        if version in seen_versions:
            exclude(item, "duplicate_article_version")
            continue
        seen_versions.add(version)
        if (str(version) in membership["article_version_ids"] or str(item["article_id"]) in membership["article_ids"]
                or item["content_hash"] in reference_hashes):
            exclude(item, "held_out_reference")
            continue
        l0, l1, weak = (current.get((version, layer)) for layer in ("L0", "L1", "L2"))
        if (l0 is None or l0.label != "valid" or l1 is None or l1.label != "kenya"
                or l1.prerequisite_annotation_id != l0.id or l1.method_name != methods["L1_method_name"]):
            exclude(item, "not_current_l1_kenya")
            continue
        if (weak is None or weak.prerequisite_annotation_id != l1.id or weak.article_id != item["article_id"]
                or weak.method_name != methods["L2_method_name"] or weak.method_version != methods["L2"]):
            exclude(item, "missing_compatible_weak_label")
            continue
        review = latest.get(weak.id)
        label, label_source, reason = resolve_label(weak, review, label_policy)
        if reason:
            exclude(item, reason)
            continue
        resolved.append((item, l1, weak, review, label, label_source))
    pre_counts = dict(sorted(Counter(row[4] for row in resolved).items()))
    groups = defaultdict(list)
    for row in resolved:
        groups[row[0]["content_hash"]].append(row)
    selected = []
    for group in groups.values():
        if len({row[4] for row in group}) > 1:
            for row in group:
                exclude(row[0], "duplicate_conflicting_labels")
            continue
        # Prefer human provenance when identical bodies have identical labels.
        group.sort(key=lambda row: (row[5] == "weak_unreviewed", str(row[0]["id"])))
        selected.append(group[0])
        for row in group[1:]:
            exclude(row[0], "duplicate_body_hash", str(group[0][0]["id"]))
    records = []
    for position, (item, l1, weak, review, label, source) in enumerate(sorted(selected, key=lambda row: str(row[0]["id"])), 1):
        article = load_verified_article(item, objects)
        records.append({"article_id": str(item["article_id"]), "article_version_id": str(item["id"]),
                        "prerequisite_l1_annotation_id": str(l1.id), "l1_method_name": l1.method_name,
                        "l1_method_version": l1.method_version, "weak_annotation_id": str(weak.id),
                        "weak_method_name": weak.method_name, "weak_method_version": weak.method_version,
                        "weak_rule_version": weak.evidence["rule_version"], "machine_label": weak.label,
                        "human_validation_id": str(review["id"]) if review else None,
                        "human_guideline_version": review["guideline_version"] if review else None,
                        "review_decision": review["review_decision"] if review else None,
                        "label": label, "label_id": LABEL_MAPPING[label], "label_source": source,
                        "source": article["source"], "language": article.get("language") or None,
                        "content_hash": item["content_hash"], "dataset_membership": "development_train",
                        "input_version": INPUT_VERSION, "input": format_input(article)})
        if position % 25 == 0:
            logging.getLogger(__name__).info("l2_export policy=%s verified=%s total=%s", label_policy, position, len(selected))
    payload = "".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in records)
    digest = hashlib.sha256(payload.encode()).hexdigest()
    name = "l2-" + ("reviewed" if label_policy == "reviewed-only" else "mixed") + "-development-v1"
    manifest = {"dataset_name": name, "dataset_version": name + "-" + digest[:24],
                "kind": POLICIES[label_policy], "label_policy": label_policy, "labels_are_gold": False,
                "input_version": INPUT_VERSION, "label_mapping": LABEL_MAPPING,
                "label_provenance_vocabulary": list(LABEL_SOURCES), "weak_supervision_version": methods["L2"],
                "upstream_methods": methods, "records_file": "development.jsonl", "records_sha256": digest,
                "selected_candidate_count": len(candidates), "pre_dedup_record_count": len(resolved),
                "pre_dedup_label_counts": pre_counts, "record_count": len(records),
                "label_counts": dict(sorted(Counter(row["label"] for row in records).items())),
                "label_source_counts": {key: sum(row["label_source"] == key for row in records) for key in LABEL_SOURCES},
                "source_distribution": dict(sorted(Counter(row["source"] for row in records).items())),
                "language_distribution": dict(sorted(Counter(row["language"] or "unknown" for row in records).items())),
                "review_guideline_versions": sorted({row["human_guideline_version"] for row in records if row["human_guideline_version"]}),
                "skipped": dict(sorted(skipped.items())), "exclusions": sorted(exclusions, key=lambda row: (row["article_version_id"], row["reason"])),
                "selection_limit": limit, "split_status": "development_only_no_reference_or_heldout_test",
                "held_out_reference_status": reference_status, "reference_manifest_sha256": reference_hash,
                "validation_status": NO_VALIDATION, "deduplication": "exact_body_hash; near_duplicate_syndication_not_implemented"}
    output.mkdir(parents=True, exist_ok=False)
    (output / "development.jsonl").write_text(payload, encoding="utf-8")
    (output / "dataset_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def load_development(dataset_dir, expected_version=None):
    """Validate development-only kinds, exact provenance, counts and membership."""
    path = Path(dataset_dir)
    manifest = json.loads((path / "dataset_manifest.json").read_text())
    policy = manifest.get("label_policy")
    if (policy not in POLICIES or manifest.get("kind") != POLICIES[policy]
            or manifest.get("labels_are_gold") is not False or manifest.get("input_version") != INPUT_VERSION
            or manifest.get("label_mapping") != LABEL_MAPPING
            or manifest.get("split_status") != "development_only_no_reference_or_heldout_test"
            or manifest.get("records_file") != "development.jsonl"):
        raise ValueError("Training requires a supported development manifest, not reference/test data")
    if expected_version and manifest["dataset_version"] != expected_version:
        raise ValueError("Training dataset version mismatch")
    if sha256_file(path / "development.jsonl") != manifest["records_sha256"]:
        raise ValueError("Development dataset checksum mismatch")
    records = [json.loads(line) for line in (path / "development.jsonl").read_text().splitlines() if line]
    if len(records) != manifest["record_count"] or not records:
        raise ValueError("Empty or inconsistent development dataset")
    seen, hashes = set(), set()
    for row in records:
        origin = row.get("label_source")
        if (row.get("label") not in LABEL_MAPPING or row.get("label_id") != LABEL_MAPPING[row["label"]]
                or row.get("weak_method_version") != manifest["weak_supervision_version"]
                or row.get("l1_method_version") != manifest["upstream_methods"]["L1"]
                or row.get("weak_method_name") != manifest["upstream_methods"]["L2_method_name"]
                or row.get("l1_method_name") != manifest["upstream_methods"]["L1_method_name"]
                or row.get("dataset_membership") != "development_train" or row.get("input_version") != INPUT_VERSION
                or not isinstance(row.get("input"), str) or origin not in LABEL_SOURCES
                or any(not row.get(key) for key in ("article_id", "article_version_id", "prerequisite_l1_annotation_id", "weak_annotation_id", "content_hash"))):
            raise ValueError("Invalid development row/lineage")
        if origin == "weak_unreviewed":
            if policy == "reviewed-only" or row.get("human_validation_id") or row.get("review_decision") or row["label"] != row.get("machine_label"):
                raise ValueError("Invalid weak-unreviewed provenance")
        elif (not row.get("human_validation_id") or not row.get("human_guideline_version")
              or row.get("review_decision") != origin.removeprefix("human_")
              or origin == "human_confirmed" and row["label"] != row.get("machine_label")):
            raise ValueError("Invalid human provenance")
        if row["article_version_id"] in seen or row["content_hash"] in hashes:
            raise ValueError("Duplicate development membership")
        seen.add(row["article_version_id"])
        hashes.add(row["content_hash"])
    for key, field in (("label_counts", "label"), ("label_source_counts", "label_source"),
                       ("source_distribution", "source"), ("language_distribution", "language")):
        actual = Counter(row[field] or "unknown" for row in records)
        reported = {k: v for k, v in manifest[key].items() if v}
        if dict(actual) != reported:
            raise ValueError("Development manifest counts mismatch")
    if {row["label"] for row in records} != set(LABEL_MAPPING):
        raise ValueError("Binary development training requires examples from both classes")
    return records, manifest
