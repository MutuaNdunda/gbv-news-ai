"""One annotation orchestration API for CLI, bounded UI, and future automation."""

from dataclasses import asdict
import hashlib
import json
import logging
from time import perf_counter
from urllib.parse import urlsplit
from uuid import UUID

from annotations.l0 import evaluate_l0, gcs_reference
from annotations.l1 import evaluate_l1
from annotations.schemas import DEFAULT_CONFIG
from database.repositories.annotations import AnnotationLockLost


LOGGER = logging.getLogger(__name__)


def log_event(event, **fields):
    LOGGER.info("%s %s", event, " ".join(f"{name}={value}" for name, value in fields.items()))


def load_article(candidate, objects):
    """Read only the configured processed bucket and exact stored generation."""
    uri = candidate["processed_object_uri"]
    record = None
    if gcs_reference(uri):
        parsed = urlsplit(uri)
        if parsed.netloc != objects.buckets["processed"]:
            raise ValueError("Processed reference points outside configured bucket")
        record = objects.read_json("processed", parsed.path.lstrip("/"),
                                   generation=candidate["processed_object_generation"])
        if record is not None and not isinstance(record, dict):
            raise ValueError("Processed object is not an article mapping")
    item = dict(candidate["metadata"])
    if record:
        item.update(record)
    errors = []
    if record:
        for field in ("source", "canonical_url"):
            if record.get(field) != candidate["metadata"].get(field): errors.append(f"{field}_lineage_mismatch")
        for field in ("content_hash", "parser_version"):
            if record.get(field) != candidate[field]: errors.append(f"{field}_lineage_mismatch")
    item.update({field: candidate[field] for field in ("raw_object_uri", "processed_object_uri", "content_hash", "parser_version")})
    item["processed_object_missing"] = record is None
    item["lineage_errors"] = errors
    return item


def run_annotation_pipeline(layers=("L0", "L1"), limit=None, article_ids=None,
                            collection_run_id=None, only_pending=True, trigger_type="cli",
                            config=DEFAULT_CONFIG, services=None):
    layers = sorted(set(layer.upper() for layer in layers))
    if not layers or any(layer not in ("L0", "L1") for layer in layers):
        raise ValueError("Only L0 and L1 annotation layers are implemented")
    if limit is not None and (isinstance(limit, bool) or limit < 1):
        raise ValueError("Limit must be positive")
    if trigger_type not in ("cli", "manual_ui", "post_collection", "scheduled"):
        raise ValueError("Unsupported annotation trigger")
    article_ids = [UUID(str(value)) for value in article_ids] if article_ids else None
    collection_run_id = UUID(str(collection_run_id)) if collection_run_id else None
    if services is None:
        from database.repositories.annotations import AnnotationRepository
        from database.session import create_session_factory
        from storage import GCSStorage
        services = AnnotationRepository(create_session_factory()), GCSStorage()
    repository, objects = services
    methods = {layer: config.method_version(layer) for layer in ("L0", "L1")}
    configuration = {"parameters": asdict(config), "limit": limit, "only_pending": only_pending,
                     "article_ids": [str(value) for value in article_ids or []],
                     "collection_run_id": str(collection_run_id) if collection_run_id else None}
    started = perf_counter()
    summary = {"requested": 0, "processed": 0, "success": 0, "failed": 0, "skipped": 0,
               "layers": {layer: {"eligible": 0, "processed": 0, "skipped": 0, "failed": 0,
                                  "skipped_l0": 0, "labels": {}} for layer in layers}, "errors": []}
    with repository.lock() as lease:
        run_id = repository.create_run(layers, methods, trigger_type, collection_run_id, configuration)
        summary["run_id"] = str(run_id)
        log_event("annotation_run_started", annotation_run_id=run_id, layers=",".join(layers), trigger=trigger_type)
        try:
            candidates = repository.select_candidates(layers, methods, limit, article_ids,
                                                       collection_run_id, only_pending)
            summary["requested"] = len(candidates)
            repository.set_selection(run_id, candidates)
            current = repository.current_for_candidates([item["id"] for item in candidates], methods)
            for candidate in candidates:
                if lease is not None:
                    lease.check()
                summary["processed"] += 1
                wrote = False
                layer = layers[0]
                input_article = None
                try:
                    l0 = current.get((candidate["id"], "L0"))
                    for layer in layers:
                        stats = summary["layers"][layer]
                        fields = {"annotation_run_id": run_id, "article_id": candidate["article_id"],
                                  "article_version_id": candidate["id"], "method_version": methods[layer]}
                        if layer == "L1" and (l0 is None or l0.label != "valid"):
                            stats["skipped"] += 1
                            stats["skipped_l0"] += 1
                            log_event("l1_skipped", **fields, reason="l0_not_valid")
                            continue
                        stats["eligible"] += 1
                        previous = l0 if layer == "L0" else current.get((candidate["id"], "L1"))
                        if layer == "L1" and previous is not None and previous.prerequisite_annotation_id != l0.id:
                            previous = None
                        if only_pending and previous is not None:
                            stats["skipped"] += 1
                            log_event(f"{layer.lower()}_skipped", **fields, reason="current_version_exists")
                            continue
                        tick = perf_counter()
                        log_event(f"{layer.lower()}_started", **fields)
                        if input_article is None: input_article = load_article(candidate, objects)
                        if layer == "L1":
                            body = input_article.get("article_text")
                            if (input_article["processed_object_missing"] or input_article["lineage_errors"]
                                    or not isinstance(body, str)
                                    or hashlib.sha256(body.encode("utf-8")).hexdigest() != candidate["content_hash"].lower()):
                                raise ValueError("L1 input no longer matches the version accepted by L0")
                        result = evaluate_l0(input_article, config) if layer == "L0" else evaluate_l1(input_article, config)
                        if lease is not None:
                            lease.check()
                        annotation = repository.persist(candidate, run_id, result, l0.id if layer == "L1" else None)
                        if layer == "L0": l0 = annotation
                        wrote = True
                        stats["processed"] += 1
                        stats["labels"][result.label] = stats["labels"].get(result.label, 0) + 1
                        log_event(f"{layer.lower()}_completed", **fields, label=result.label,
                                  confidence=result.confidence, duration_ms=round((perf_counter() - tick) * 1000, 2))
                    summary["success" if wrote else "skipped"] += 1
                except Exception as exc:
                    summary["failed"] += 1
                    summary["layers"][layer]["failed"] += 1
                    error = {"article_id": str(candidate["article_id"]), "article_version_id": str(candidate["id"]),
                             "layer": layer, "error_type": type(exc).__name__}
                    summary["errors"].append(error)
                    log_event(f"{layer.lower()}_failed", annotation_run_id=run_id, **error)
                    # Losing serialization is a run-wide failure; do not continue writes.
                    if isinstance(exc, AnnotationLockLost):
                        raise
                summary["duration_ms"] = round((perf_counter() - started) * 1000, 2)
                repository.checkpoint(run_id, summary)
            status = ("failed" if summary["failed"] and summary["failed"] == summary["requested"] else
                      "completed_with_errors" if summary["failed"] else "completed")
            summary.update(status=status, duration_ms=round((perf_counter() - started) * 1000, 2))
            repository.checkpoint(run_id, summary, status)
            log_event("annotation_run_failed" if status == "failed" else "annotation_run_completed",
                      annotation_run_id=run_id, status=status,
                      requested=summary["requested"], processed=summary["processed"], success=summary["success"],
                      failed=summary["failed"], skipped=summary["skipped"], duration_ms=summary["duration_ms"],
                      labels=json.dumps({key: value["labels"] for key, value in summary["layers"].items()}, sort_keys=True))
        except BaseException as exc:
            status = "interrupted" if isinstance(exc, (KeyboardInterrupt, SystemExit)) else "failed"
            summary.update(status=status, duration_ms=round((perf_counter() - started) * 1000, 2))
            summary["errors"].append({"error_type": type(exc).__name__})
            try:
                repository.checkpoint(run_id, summary, status)
            except Exception:
                log_event("annotation_run_failed", annotation_run_id=run_id, reason="checkpoint_failed")
            log_event("annotation_run_failed", annotation_run_id=run_id, error_type=type(exc).__name__)
            raise
    return summary
