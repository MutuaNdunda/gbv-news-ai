# L2 transformer development performance

## Current coverage observation — 8 October 2026, audit beginning 22:50 EAT

The same configured dev-v1 artifact now has **1,417/1,417** compatible eligible
predictions: **246 gbv / 1,049 not_gbv / 122 borderline**, zero eligible pending.
Upstream L0/L1 covers the expanded 2,119-version observation. Training remains
322 records; no retraining or model/threshold change is asserted by this audit.
Validation schema is ready; zero real reference batches/members exist and independent
accuracy/precision/recall/F1/calibration remain unmeasured. Metadata screening
finds 1,089 potentially unseen formal-source candidates, with Standard zero, before
full object/language/period/duplicate-family/exposure checks. See
[dataset creation](research/validation_dataset_creation.md) for the next assessment.
The historical 324-prediction operational closure below is retained as dated evidence.

## Scope and evidence

This report covers `l2-afroxlmr-dev-v1`, method
`afroxlmr_gbv_relevance` / `l2-47035d92f81cd5240062610d`.
Final development verification: **6 October 2026, 00:04 EAT**: 324/324 compatible
model results, zero pending, schema ready. Earlier read-only observations at
22:43/22:59 EAT on 5 October are retained below as historical evidence.
Evidence for the historical baseline is its dated compatible annotation aggregate, persisted annotation-run
summary, private training manifest and bounded offline-reload report. No private
article text, reviewer identities or per-article identifiers are published here.

This is **initial development evidence**. Model output counts are not accuracy,
verified incident counts or validated GBV prevalence. No independent held-out
human evaluation has been performed; accuracy, precision, recall, F1, AUC and
calibration are **not established**. L2 research stage gates remain open.

**7 October documentation update:** the researcher confirmed L2 codebook v1.0
finalization. This semantic milestone does not add model-evaluation evidence.
Shared archive collection and parser corrections are documented in the
implementation log; the counts in this report remain the dated development
baseline. Sampling/acceptance design, independent review and evaluation remain
the next research work.

### L2 operational milestone closed — 6 October 2026, 00:04 EAT

**L2 DEVELOPMENT MODEL COVERAGE is complete: 324/324
compatible predictions, zero pending.** Final model labels are
**gbv 11 / not_gbv 307 / borderline 6**.
This closes operational coverage, not the L2 research-validation gate.

The read-only baseline used the same documented development database configured
by repository-local `.env`: PostgreSQL/psycopg, Supabase session pooler
`aws-1-eu-west-1.pooler.supabase.com:5432`, database `postgres`. No production
configuration was used. Baseline: 536 article versions; L0 valid 519/review 17;
L1 v2 kenya 324/not_kenya 35/ambiguous 160; model 300/324 with 10/284/6 and 24 pending.
Original weak counts were 7/15/302, effective weak view 10/312/2; human-validation
rows were L1 1 and L2 302 (303 total). Those upstream/human records were preserved.

**Artifact verified unchanged:** `l2-afroxlmr-dev-v1`, method
`l2-47035d92f81cd5240062610d`, the existing binary order and 0.8/0.2 engineering
thresholds. Manifest, config, tokenizer and safetensors checksums passed; offline
local-files-only reload with remote code disabled, `eval()` and a synthetic
`inference_mode()` forward pass succeeded. The validation reload took
3.338 seconds on cpu; this is a separate artifact check,
not model-load timing from the resume runs. No data regeneration, retraining,
new model identity, tokenizer change or threshold tuning occurred.

**Migration:** preflight inspected all 624 historical L2 weak/model rows. Invalid
labels, NULL/missing prerequisites, non-L1 prerequisites, cross-article,
cross-version and non-Kenya prerequisite counts were all **zero**. Expected-name
conflicts were zero, including the trigger function. The exact additive
`20261005_add_l2_annotations.sql` was applied to the confirmed development target
at 2026-10-05T20:25:03.711181+00:00 using existing SQLAlchemy/psycopg credentials (`psql` was
unavailable and `DIRECT_DATABASE_URL` unset). No history rows were repaired or
rewritten. Schema readiness is now **true**. Installed objects:

- `automated_annotations_l2_label_check`;
- `automated_annotations_l2_prerequisite_check`;
- `idx_auto_annotations_l2_identity`;
- `validate_l2_prerequisite()` and trigger `automated_annotations_l2_prerequisite`.

Rolled-back synthetic behavior tests accepted valid L2 lineage and rejected an
invalid label, NULL prerequisite, non-L1/non-Kenya prerequisite and wrong
article/version. All synthetic articles, versions, run and test annotations were
rolled back. No private article content was used in these schema tests.

**Failure diagnosis:** macOS power-management evidence records idle sleep at
**16:25:50** and wake at **16:33:26** on 5 October; the earlier failed run ended at
**16:33:29**, three seconds later. This strongly supports host sleep disrupting the
live database connections, and explains the active-time/wall-time discrepancy.
Source inspection locates the first caught `OperationalError` in prediction
persistence; the next dedicated-connection check raised `AnnotationLockLost`, a
secondary fail-closed stop. The old run retained exception types only: its exact
socket/server message and SQLSTATE cannot be recovered, so no specific server
termination mechanism is claimed. Current PostgreSQL idle-session and
idle-transaction timeouts are zero; the configured connection is session mode,
not rejected transaction pooling. No lock checks were disabled to finish.

**Minimal reliability changes:** macOS model CLI runs now hold a scoped
`caffeinate -i -w <CLI-PID>` idle-sleep assertion through loading/inference/writes,
with cleanup on success or failure. This prevents automatic idle sleep; forced
sleep/network interruption can still lose the connection and correctly stop a run.
L2 execution checks installed schema before creating a run or prediction rows.
Lease checks now verify both original backend PID and actual exclusive ownership
of the specific advisory lock in `pg_locks`. A lost connection is invalidated;
cleanup does not reconnect to unlock a replacement session. No automatic relock,
force mode or database write replay was introduced. Safe diagnostics now retain
failure phase, SQLSTATE where supplied, connection-invalidated flag and a separate
`wall_duration_ms`, without SQL, parameters, error messages or article text.

**Executed resume:** a precise five-article pending-only pass saved five not-GBV
results, verified unchanged history, then the normal unbounded pending-only command
finished the remaining eligible records:

```bash
.venv/bin/python scripts/run_annotations.py --layer l2 --l2-mode model
```

The bounded pass used five live pending article IDs through existing repeatable
`--article-id` filters; private IDs are not published here. Both passes used the
existing artifact/configuration, batch size 2 and no `--force`, weak, L0 or L1
execution. The unbounded pending selector also scans versions gated out by L1;
those are accounted as skips and did not receive new predictions.

| Pass | Selected | Processed | Saved | Skipped | Failed | Run duration | Wall duration | Inference + loading | Stage average / saved |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Five-article pass | 5 | 5 | 5 | 0 | 0 | 20.097 s | 20.097 s | 4.734 s | 946.728 ms |
| Remaining pending-only pass | 231 | 231 | 19 | 212 | 0 | 276.064 s | 276.063 s | 14.278 s | 751.481 ms |

New predictions total **24**: gbv
1, not_gbv 23, borderline
0. Both runs completed with zero recorded failures.
`inference_and_loading_ms` includes verified object retrieval and batched inference;
its average is **not pure transformer latency** or proof of the thesis <500 ms
inference target. Overall duration includes selection, gates, lock checks,
persistence and checkpoints, and starts after artifact initialization/schema reads.

**Integrity proof:** private before/after row fingerprints verified all **300**
pre-existing model predictions remain unchanged and current, all **2,218**
pre-existing automated annotation rows unchanged (including weak and L1 history),
all **303** human-validation rows unchanged, and all **536** article versions
unchanged. Only 24 pending-compatible L2 rows were added. There are **zero**
duplicate current-compatible groups or unexpected force/history rows. Every current
model result uses the same identity/thresholds and exact current same-article,
same-version L1-Kenya prerequisite. Artifact hashes are unchanged. Private evidence
is stored under ignored `data/l2/operational-close-20261005/`.

**Verification:** 47 targeted schema/L2/pipeline/lock tests passed; full offline suite
with explicitly installed-model integration **275 passed**, zero failures/skips.
The 11 new operational tests cover missing-schema refusal, installed-schema success,
macOS guard cleanup/failure, actual lock ownership, connection invalidation, safe
SQLSTATE/phase logging, transient member failure and partial resume, retention of
300 results with only 24 added, and lost-lease write refusal. Existing batch/member,
exact prerequisite, pending/force history and threshold tests passed unchanged in
behavior. `git diff --check`, private-data/model/.env exclusions and Markdown links
passed. New model probabilities are operational outputs, not reference labels.

**Remaining research limitations:** only 10 positive training examples (three
human-reviewed), no independent protected reference set, no calibrated thresholds,
no independently measured accuracy/precision/recall/F1/AUC. L0/L1 validation and
reference design remain open. No L3/L4, NER, geocoding, active learning, corpus
expansion or retraining was started. The next milestone is independently designed
human validation and improved positive/reference support under separate authorization.

## Historical interrupted inference run — before closure

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
span approximately **25m42.706s**. The later diagnosis strongly associates this
discrepancy with idle sleep; the exact driver disconnect message is unavailable. The recorded batched inference-and-loading stage took
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

**Historical schema readiness was false:** the expected L2 label constraint, prerequisite
constraint, method/dependency index and L1-Kenya prerequisite trigger from
`20261005_add_l2_annotations.sql` were absent. Existing persisted predictions
did not establish installation. The closure above subsequently applied and tested
the migration and completed pending-only prediction writes without `--force`.

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

1. Operational closure is complete: schema and 324/324 compatible coverage are
   verified. Preserve fail-closed leases and pending-only recovery for future runs.
2. Use L2 codebook v1.0, finalized by researcher confirmation on 7 October 2026.
   Expand independently reviewed positives/source-language coverage, agree sampling
   and acceptance criteria, and validate L0/L1 eligibility.
3. Group near duplicates and freeze an independent human-reference set excluded
   from training and tuning.
4. Agree evaluation support/acceptance criteria, then measure per-class precision,
   recall, F1, macro-F1, confusion counts and AUC where defensible, plus calibration
   and source/language error analysis. Tune thresholds on development validation
   only, preserving the independent final reference set.

## Validation engineering and remaining research work

Operational coverage is complete. The
[structured L2 validation workflow](annotations.md#22-l2-validation-and-protected-reference-workflow)
now implements reproducible batches, blind initial decisions, protected training
exclusion and deterministic private evaluation. The new migration is **installed
and behavior-verified in development** on 6 October at 23:48 EAT; 15 rollback-only
guard checks passed, readiness is true and existing fingerprints are unchanged.
No real independent batch or research scores were generated.
All 322 actual training articles/versions/hashes are excluded from independent
selection; training reviews are diagnostic error analysis. Near-duplicate grouping,
independent A/B review and separate adjudication records remain pending. Codebook
finalization is complete; agree sampling design, verify other targets independently, and collect sufficient unseen
positive support before performance claims. The 6 October engineering suite: **304 tests
passed**, including installed-artifact integration, zero failures/skips. No
retraining or threshold calibration was performed.
