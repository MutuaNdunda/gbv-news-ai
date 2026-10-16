# Markdown documentation audit — 16 October 2026

Reviewed all **20 pre-existing tracked Markdown files** for current lifecycle, next-stage guidance and applicability of training enrichment. This audit does not inspect or publish private research Markdown under ignored `data/`.

Before editing, most main guides already recorded the 13 October completion and private evaluation. Gaps included stale active first-batch instructions, an older immediate-next-steps list, and no shared training-enrichment plan. Dated engineering observations are preserved as history.

| Document | Outcome |
| --- | --- |
| [AGENTS.md](../AGENTS.md) | Updated relevant handoff, planning guidance or historical/current-status distinction; frozen semantic definitions preserved. |
| [README.md](../README.md) | Updated relevant handoff, planning guidance or historical/current-status distinction; frozen semantic definitions preserved. |
| [annotations/resources/upstream/alvin/README.md](../annotations/resources/upstream/alvin/README.md) | Reviewed; unchanged third-party provenance/resource instructions, unrelated to model-training status. |
| [annotations/resources/upstream/david/README.md](../annotations/resources/upstream/david/README.md) | Reviewed; unchanged third-party provenance/resource instructions, unrelated to model-training status. |
| [annotations/resources/upstream/tiga/README.md](../annotations/resources/upstream/tiga/README.md) | Reviewed; unchanged third-party provenance/resource instructions, unrelated to model-training status. |
| [docs/AI_CONTEXT.md](../docs/AI_CONTEXT.md) | Updated relevant handoff, planning guidance or historical/current-status distinction; frozen semantic definitions preserved. |
| [docs/annotations.md](../docs/annotations.md) | Updated relevant handoff, planning guidance or historical/current-status distinction; frozen semantic definitions preserved. |
| [docs/app_engine_deployment.md](../docs/app_engine_deployment.md) | Reviewed; existing 13 October status is aligned. Deployment, collection-control or dated Git instructions need no enrichment-specific change. |
| [docs/bulk_l2_validation.md](../docs/bulk_l2_validation.md) | Updated relevant handoff, planning guidance or historical/current-status distinction; frozen semantic definitions preserved. |
| [docs/collection_protocol.md](../docs/collection_protocol.md) | Updated relevant handoff, planning guidance or historical/current-status distinction; frozen semantic definitions preserved. |
| [docs/collection_run_control.md](../docs/collection_run_control.md) | Reviewed; existing 13 October status is aligned. Deployment, collection-control or dated Git instructions need no enrichment-specific change. |
| [docs/git_push_diagnostic.md](../docs/git_push_diagnostic.md) | Reviewed; existing 13 October status is aligned. Deployment, collection-control or dated Git instructions need no enrichment-specific change. |
| [docs/l2_model_performance.md](../docs/l2_model_performance.md) | Updated relevant handoff, planning guidance or historical/current-status distinction; frozen semantic definitions preserved. |
| [docs/l2_model_performance_dashboard.md](../docs/l2_model_performance_dashboard.md) | Updated relevant handoff, planning guidance or historical/current-status distinction; frozen semantic definitions preserved. |
| [docs/research/l2_gbv_relevance_codebook_v1.0.md](../docs/research/l2_gbv_relevance_codebook_v1.0.md) | Updated relevant handoff, planning guidance or historical/current-status distinction; frozen semantic definitions preserved. |
| [docs/research/l2_human_validation_progress_20261013.md](../docs/research/l2_human_validation_progress_20261013.md) | Updated relevant handoff, planning guidance or historical/current-status distinction; frozen semantic definitions preserved. |
| [docs/research/l2_validation_sampling_protocol_v1.0.md](../docs/research/l2_validation_sampling_protocol_v1.0.md) | Updated relevant handoff, planning guidance or historical/current-status distinction; frozen semantic definitions preserved. |
| [docs/research/validation_dataset_creation.md](../docs/research/validation_dataset_creation.md) | Updated relevant handoff, planning guidance or historical/current-status distinction; frozen semantic definitions preserved. |
| [docs/roadmap/IMPLEMENTATION_STATUS.md](../docs/roadmap/IMPLEMENTATION_STATUS.md) | Updated relevant handoff, planning guidance or historical/current-status distinction; frozen semantic definitions preserved. |
| [docs/roadmap/README.md](../docs/roadmap/README.md) | Updated relevant handoff, planning guidance or historical/current-status distinction; frozen semantic definitions preserved. |

## Shared new guidance

[L2 training enrichment and next development cycle](research/l2_training_enrichment_plan.md) records proposed 30–50% positive training composition and several hundred body-reviewed positives as experiment suggestions, not approved quotas. It describes broad plus targeted collection, URL-only matching, hard negatives, lineage and protected train/development/final-test separation.

## Verification and limits

- Roadmap remote check: `.venv/bin/python scripts/sync_roadmap.py --check`, exit 0; all four exports match. The canonical Sheet retains older planning statements. No CSV was manually edited or Sheet written.
- Checked changed Markdown for whitespace errors and newly introduced local file links. Historical existing links are outside this change.
- Preserved codebook/protocol semantic versions, original frozen instrument identities and sealed v1 references. Operational addenda do not assert research approval.
- No application code, schema, configuration, dataset, private scores or model artifact changed. No collection, inference, evaluation or training executed.
- Existing test counts remain dated evidence; a software test suite is unnecessary for these documentation-only edits.
