# L2 transformer development performance

## Scope and evidence

This report covers `l2-afroxlmr-dev-v1`, method
`afroxlmr_gbv_relevance` / `l2-47035d92f81cd5240062610d`.
Read-only development database verification: **5 October 2026, 22:43 EAT**.
Evidence is the current compatible annotation aggregate, persisted annotation-run
summary, private training manifest and bounded offline-reload report. No private
article text, reviewer identities or per-article identifiers are published here.

This is **initial development evidence**. Model output counts are not accuracy,
verified incident counts or validated GBV prevalence. No independent held-out
human evaluation has been performed; accuracy, precision, recall, F1, AUC and
calibration are **not established**. L2 research stage gates remain open.

## Latest persisted inference run

| Measure | Verified result |
| --- | ---: |
| Current L1-Kenya eligible versions | 324 |
| Compatible transformer predictions saved | 300 |
| Eligible coverage | 92.59% |
| Remaining eligible versions | 24 |
| Predicted `gbv` | 10 |
| Predicted `not_gbv` | 284 |
| Predicted `borderline` | 6 |
| Run status | failed; partial results retained |
| Selected candidates | 536 |
| Candidates processed before termination | 489 |
| Successfully saved predictions | 300 |
| Recorded article failure | 1 |
| Recorded prerequisite skips | 188 |

The CLI's 536 selected candidates include versions that are not eligible for L2.
Recorded skips were 139 L1-ambiguous, 32 L1-not-Kenya and 17 missing compatible L1.
These are the skips encountered before termination, not complete corpus totals.
The run reached 301 eligible candidates, saved 300 predictions, recorded an
`OperationalError` for one candidate and then terminated with `AnnotationLockLost`.
The remaining 24 eligible versions must not be described as 24 failed predictions.
Historical output and human reviews were preserved. No retry or new inference was
performed during this documentation audit.

Run start/completion timestamps: **16:07:47–16:33:29 EAT** on 5 October.
Stored `duration_ms` is **1,093,564.96 ms (18m13.565s)**, while persisted timestamps
span approximately **25m42.706s**. This discrepancy is retained without assigning
an unsupported cause. The recorded batched inference-and-loading stage took
**227,626.81 ms (3m47.627s)**. It includes verified article loading and batched
inference; it is not pure per-article model latency or overall end-to-end latency.

| Publisher | Saved transformer predictions |
| --- | ---: |
| Citizen | 118 |
| Kenyans.co.ke | 2 |
| Nation | 16 |
| Standard | 13 |
| Star | 14 |
| Taifa Leo | 89 |
| Tuko | 48 |
| Total | 300 |

**Schema readiness remains false:** the expected L2 label constraint, prerequisite
constraint, method/dependency index and L1-Kenya prerequisite trigger from
`20261005_add_l2_annotations.sql` are all absent. Existing persisted predictions
do not establish installation. This audit did not install the migration or modify
annotations. Resolve schema readiness through the operator workflow before further
prediction writes; then resume pending records with the CLI without `--force`.

## Training diagnostics

The pinned base/tokenizer is `Davlan/afro-xlmr-base` revision
`25f27299c247a6b73a767bd82d12444138b19337`. Training used **322 mixed-effective
binary records: 10 GBV / 312 not-GBV**, comprising 300 human corrections and 22
unreviewed weak labels. Only **three positive examples are human-reviewed**.
Two human-confirmed borderline records were excluded. There were no exact duplicate
or unresolved exclusions. Near-duplicate/syndication grouping remains pending.

No arbitrary validation split was created: the entire usable development pool was
used for fitting. **No final held-out human reference set is frozen.** Severe
positive-class imbalance prevents reliable independent development metrics here.
Training loss is an optimization diagnostic; it is not classification performance.

| Training setting / diagnostic | Value |
| --- | --- |
| Device | Apple MPS; CUDA unavailable |
| Libraries | PyTorch 2.14.1; Transformers 4.57.6; safetensors 0.8.0 |
| Optimizer | AdamW |
| Epochs / steps | 3 / 483 |
| Batch / maximum input length | 2 / 512 tokens |
| Learning rate / weight decay / seed | 2e-5 / 0.01 / 42 |
| Class weighting | balanced: N / (2 × class support) |
| GBV / not-GBV weights | 16.1 / 0.5160256410256411 |
| Mean weighted training loss | 0.5048725078 |
| Epoch mean losses | 0.7354258622; 0.5244470051; 0.2547446561 |
| Training duration | 622.895 seconds (10m23s) |
| Peak memory | not measured |

Weighted per-example loss is summed and divided by the minibatch example count.
Input remains deterministic TITLE/ARTICLE with head truncation. Binary output
order is `not_gbv=0, gbv=1`. Application thresholds remain **unvalidated engineering
thresholds**: GBV at p ≥ 0.8, not-GBV at p ≤ 0.2, borderline otherwise.
Probabilities are uncalibrated softmax outputs.

## Engineering verification

The earlier bounded check reloaded the saved safetensors/tokenizer locally with
Hub access disabled, validated artifact checksums and label order, and used
`trust_remote_code=False`, `eval()` and `inference_mode()`.

| Bounded check | Result |
| --- | --- |
| Real records / publishers | 20 / 7 |
| GBV / not-GBV / borderline | 0 / 19 / 1 |
| Failures | 0 |
| Mean / median per-record inference | 120.482 / 81.057 ms |
| Artifact load time | 3.449 seconds |
| Full engineering suite including installed-model integration | 264 passed, no skips |

The bounded check differs from the larger persisted run in sample and execution
mode. Its latency is not a directly comparable whole-corpus throughput measure.
Neither run evaluates correctness against independent reference labels.

Private artifact: `models/artifacts/l2-afroxlmr-dev-v1/`. Dataset versions, hashes,
provenance and individual artifact SHA-256s are recorded in the private manifests
and the [executed development-model log](roadmap/IMPLEMENTATION_STATUS.md).
Weights, training records, private reports and `.env` remain excluded from Git.

## Required work before research evaluation

1. Resolve the required L2 schema and investigate the connection/lock interruption;
   complete the 24 pending eligible predictions and verify coverage.
2. Expand independently reviewed positives and source/language coverage; approve
   the versioned GBV codebook and validate L0/L1 eligibility.
3. Group near duplicates and freeze an independent human-reference set excluded
   from training and tuning.
4. Agree evaluation support/acceptance criteria, then measure per-class precision,
   recall, F1, macro-F1, confusion counts and AUC where defensible, plus calibration
   and source/language error analysis. Tune thresholds on development validation
   only, preserving the independent final reference set.
