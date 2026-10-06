"""One annotation orchestration API for CLI, bounded UI, and future automation."""

from dataclasses import asdict
import hashlib
import json
import logging
from time import perf_counter, time
from urllib.parse import urlsplit
from uuid import UUID

from annotations.l0 import evaluate_l0, gcs_reference
from annotations.l1 import evaluate_l1
from annotations.schemas import DEFAULT_CONFIG
from database.repositories.annotations import AnnotationLockLost


LOGGER = logging.getLogger(__name__)


def log_event(event, **fields):
    LOGGER.info("%s %s", event, " ".join(f"{name}={value}" for name, value in fields.items()))


def failure_details(exc, phase):
    """Retain useful database diagnostics without SQL, parameters or error messages."""
    from sqlalchemy.exc import DBAPIError
    details = {"error_type": type(exc).__name__, "failure_phase": phase}
    cause = exc if isinstance(exc, DBAPIError) else exc.__cause__
    if isinstance(cause, DBAPIError):
        state = getattr(cause.orig, "sqlstate", None)
        if isinstance(state, str) and len(state) == 5 and state.isalnum():
            details["sqlstate"] = state
        details["connection_invalidated"] = bool(cause.connection_invalidated)
    return details


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


def load_verified_article(candidate, objects):
    """Semantic layers consume the immutable upstream extraction, never live news."""
    article = load_article(candidate, objects)
    body = article.get("article_text")
    if (article["processed_object_missing"] or article["lineage_errors"] or not isinstance(body, str)
            or hashlib.sha256(body.encode("utf-8")).hexdigest() != candidate["content_hash"].lower()):
        raise ValueError("Annotation input no longer matches the accepted article version")
    return article


def batch_l2_results(candidates, current, objects, predictor, batch_size, lease):
    """Batch eligible L2-only inputs; isolate retrieval and model failures by version."""
    outcomes = {}
    for offset in range(0, len(candidates), batch_size):
        prepared = []
        for candidate in candidates[offset:offset + batch_size]:
            version_id = candidate["id"]
            l0, l1 = current.get((version_id, "L0")), current.get((version_id, "L1"))
            if (l0 is None or l0.label != "valid" or l1 is None or l1.label != "kenya"
                    or l1.prerequisite_annotation_id != l0.id):
                continue
            if lease is not None:
                lease.check()
            try:
                prepared.append((version_id, load_verified_article(candidate, objects)))
            except Exception as exc:
                outcomes[version_id] = exc
        if not prepared:
            continue
        try:
            results = predictor.predict_batch([article for _, article in prepared])
            if len(results) != len(prepared):
                raise ValueError("L2 batch result count mismatch")
            outcomes.update((version_id, result) for (version_id, _), result in zip(prepared, results))
        except Exception:
            # A failed batch must not prevent other individual inputs succeeding.
            for version_id, article in prepared:
                try:
                    outcomes[version_id] = predictor.evaluate(article)
                except Exception as exc:
                    outcomes[version_id] = exc
    return outcomes


def run_annotation_pipeline(layers=("L0", "L1"), limit=None, article_ids=None,
                            collection_run_id=None, only_pending=True, trigger_type="cli",
                            config=DEFAULT_CONFIG, services=None, l2_mode="model", l2_config=None,
                            l2_predictor=None):
    layers = sorted(set(layer.upper() for layer in layers))
    if not layers or any(layer not in ("L0", "L1", "L2") for layer in layers):
        raise ValueError("Only L0, L1 and L2 annotation layers are implemented")
    if limit is not None and (isinstance(limit, bool) or limit < 1):
        raise ValueError("Limit must be positive")
    if trigger_type not in ("cli", "manual_ui", "post_collection", "scheduled"):
        raise ValueError("Unsupported annotation trigger")
    article_ids = [UUID(str(value)) for value in article_ids] if article_ids else None
    collection_run_id = UUID(str(collection_run_id)) if collection_run_id else None
    methods = {layer: config.method_version(layer) for layer in ("L0", "L1")}
    if "L2" in layers:
        from annotations.l2 import get_predictor
        from annotations.l2_config import L1_METHOD, L2Config
        from database.session import load_environment
        load_environment()
        l2_config = l2_config or L2Config.from_env()
        l2_predictor = l2_predictor or get_predictor(l2_mode, l2_config)
        methods.update(L2=l2_predictor.method_version, L2_method_name=l2_predictor.method_name,
                       L1_method_name=L1_METHOD)
    if services is None:
        from database.repositories.annotations import AnnotationRepository
        from database.session import create_session_factory
        from storage import GCSStorage
        services = AnnotationRepository(create_session_factory()), GCSStorage()
    repository, objects = services
    if "L2" in layers:
        repository.ensure_l2_schema()
    configuration = {"parameters": asdict(config), "limit": limit, "only_pending": only_pending,
                     "article_ids": [str(value) for value in article_ids or []],
                     "collection_run_id": str(collection_run_id) if collection_run_id else None}
    if "L2" in layers:
        # Do not publish local artifact paths or credentials in run configuration.
        configuration["l2"] = {"mode": l2_mode, "method_name": l2_predictor.method_name,
                               "method_version": l2_predictor.method_version,
                               "positive_threshold": l2_config.positive_threshold,
                               "negative_threshold": l2_config.negative_threshold,
                               "threshold_status": "UNVALIDATED ENGINEERING THRESHOLDS"}
    started = perf_counter()
    wall_started = time()
    summary = {"requested": 0, "processed": 0, "success": 0, "failed": 0, "skipped": 0,
               "layers": {layer: {"eligible": 0, "processed": 0, "skipped": 0, "failed": 0,
                                  "skipped_l0": 0, "labels": {}} for layer in layers}, "errors": []}
    phase = "lock_acquisition"
    with repository.lock() as lease:
        run_id = repository.create_run(layers, methods, trigger_type, collection_run_id, configuration)
        summary["run_id"] = str(run_id)
        log_event("annotation_run_started", annotation_run_id=run_id, layers=",".join(layers), trigger=trigger_type)
        try:
            phase = "candidate_selection"
            candidates = repository.select_candidates(layers, methods, limit, article_ids,
                                                       collection_run_id, only_pending)
            summary["requested"] = len(candidates)
            repository.set_selection(run_id, candidates)
            current = repository.current_for_candidates([item["id"] for item in candidates], methods)
            l2_outcomes = {}
            if layers == ["L2"]:
                phase = "input_loading_and_model_inference"
                tick = perf_counter()
                pending = [item for item in candidates if not only_pending or
                           current.get((item["id"], "L2")) is None]
                l2_outcomes = batch_l2_results(pending, current, objects, l2_predictor,
                                               l2_config.batch_size, lease)
                summary["layers"]["L2"]["inference_and_loading_ms"] = round((perf_counter() - tick) * 1000, 2)
            for candidate in candidates:
                phase = "lock_health_check"
                if lease is not None:
                    lease.check()
                summary["processed"] += 1
                wrote = False
                layer = layers[0]
                input_article = None
                try:
                    l0 = current.get((candidate["id"], "L0"))
                    l1 = current.get((candidate["id"], "L1"))
                    for layer in layers:
                        stats = summary["layers"][layer]
                        fields = {"annotation_run_id": run_id, "article_id": candidate["article_id"],
                                  "article_version_id": candidate["id"], "method_version": methods[layer]}
                        if layer == "L1" and (l0 is None or l0.label != "valid"):
                            stats["skipped"] += 1
                            stats["skipped_l0"] += 1
                            log_event("l1_skipped", **fields, reason="l0_not_valid")
                            continue
                        if layer == "L2":
                            reason = ("missing_compatible_l1" if l1 is None or l0 is None
                                      or l0.label != "valid" or l1.prerequisite_annotation_id != l0.id
                                      else "l1_" + l1.label if l1.label != "kenya" else None)
                            if reason:
                                stats["skipped"] += 1
                                stats.setdefault("skip_reasons", {})[reason] = stats.get("skip_reasons", {}).get(reason, 0) + 1
                                log_event("l2_skipped", **fields, reason=reason)
                                continue
                        stats["eligible"] += 1
                        previous = l0 if layer == "L0" else l1 if layer == "L1" else current.get((candidate["id"], "L2"))
                        if layer == "L1" and previous is not None and previous.prerequisite_annotation_id != l0.id:
                            previous = None
                        if layer == "L2" and previous is not None and previous.prerequisite_annotation_id != l1.id:
                            previous = None
                        if only_pending and previous is not None:
                            stats["skipped"] += 1
                            log_event(f"{layer.lower()}_skipped", **fields, reason="current_version_exists")
                            continue
                        tick = perf_counter()
                        log_event(f"{layer.lower()}_started", **fields)
                        if layer == "L2" and candidate["id"] in l2_outcomes:
                            phase = "input_loading_or_model_inference"
                            result = l2_outcomes[candidate["id"]]
                            if isinstance(result, Exception):
                                raise result
                        else:
                            phase = "input_loading"
                            if input_article is None: input_article = load_article(candidate, objects)
                            if layer in ("L1", "L2"):
                                body = input_article.get("article_text")
                                if (input_article["processed_object_missing"] or input_article["lineage_errors"]
                                        or not isinstance(body, str)
                                        or hashlib.sha256(body.encode("utf-8")).hexdigest() != candidate["content_hash"].lower()):
                                    raise ValueError("Annotation input no longer matches the accepted article version")
                            phase = "annotation_evaluation"
                            result = (evaluate_l0(input_article, config) if layer == "L0" else
                                      evaluate_l1(input_article, config) if layer == "L1" else
                                      l2_predictor.evaluate(input_article))
                        if layer == "L2" and (result.layer != "L2" or result.label not in ("gbv", "not_gbv", "borderline")
                                              or result.method_name != methods["L2_method_name"]
                                              or result.method_version != methods["L2"]):
                            raise ValueError("L2 predictor returned an incompatible result identity")
                        phase = "lock_health_check"
                        if lease is not None:
                            lease.check()
                        phase = "prediction_persistence"
                        annotation = repository.persist(candidate, run_id, result,
                                                        l0.id if layer == "L1" else l1.id if layer == "L2" else None)
                        if layer == "L0": l0 = annotation
                        if layer == "L1": l1 = annotation
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
                             "layer": layer, **failure_details(exc, phase)}
                    summary["errors"].append(error)
                    log_event(f"{layer.lower()}_failed", annotation_run_id=run_id, **error)
                    # Losing serialization is a run-wide failure; do not continue writes.
                    if isinstance(exc, AnnotationLockLost):
                        raise
                summary["duration_ms"] = round((perf_counter() - started) * 1000, 2)
                summary["wall_duration_ms"] = round((time() - wall_started) * 1000, 2)
                phase = "run_checkpoint"
                repository.checkpoint(run_id, summary)
            status = ("failed" if summary["failed"] and summary["failed"] == summary["requested"] else
                      "completed_with_errors" if summary["failed"] else "completed")
            summary.update(status=status, duration_ms=round((perf_counter() - started) * 1000, 2),
                           wall_duration_ms=round((time() - wall_started) * 1000, 2))
            repository.checkpoint(run_id, summary, status)
            log_event("annotation_run_failed" if status == "failed" else "annotation_run_completed",
                      annotation_run_id=run_id, status=status,
                      requested=summary["requested"], processed=summary["processed"], success=summary["success"],
                      failed=summary["failed"], skipped=summary["skipped"], duration_ms=summary["duration_ms"],
                      labels=json.dumps({key: value["labels"] for key, value in summary["layers"].items()}, sort_keys=True))
        except BaseException as exc:
            status = "interrupted" if isinstance(exc, (KeyboardInterrupt, SystemExit)) else "failed"
            summary.update(status=status, duration_ms=round((perf_counter() - started) * 1000, 2),
                           wall_duration_ms=round((time() - wall_started) * 1000, 2))
            summary["errors"].append(failure_details(exc, phase))
            try:
                repository.checkpoint(run_id, summary, status)
            except Exception:
                log_event("annotation_run_failed", annotation_run_id=run_id, reason="checkpoint_failed")
            log_event("annotation_run_failed", annotation_run_id=run_id, error_type=type(exc).__name__)
            raise
    return summary
