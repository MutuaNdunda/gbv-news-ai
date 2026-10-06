# Repository implementation status

This engineering log records executed code and observations. The public Sheet
remains the planning source of truth; synchronized CSVs were not edited manually.
No private article content, victim information or reference labels belong here.

## Current Milestone

**L0/L1 implemented and executed; L2 weak bootstrap covers the current eligible
corpus; training/inference infrastructure and local L0/L1/L2 Human Review implemented.
Human review is recorded for all 302 originally borderline L2 weak results.
The first real AfroXLMR development artifact is trained/configured locally;
L2 development model coverage is complete: 324/324 compatible predictions, zero
pending; required L2 annotation schema is installed. L2 validation-batch, blind-review,
protected-reference and private-evaluator engineering is implemented; its new
validation migration is installed and behavior-verified in development.
Independent research validation remains pending.**

### Validation migration installed — 6 October 2026, 23:48 EAT

Following the user's explicit request to run installation, applied
`migrations/20261006_add_l2_validation_batches.sql` to the existing configured
development Supabase session-pooler target. Preflight confirmed both new tables,
both guard functions/triggers and conflicting expected names absent, with existing
L2 annotation/review prerequisites ready. The additive migration committed at
`2026-10-06T20:48:21.941476+00:00`. SQL SHA-256:
`d8e586964cea95697f1a974cb9676aef23d951c3086d3480f09b92dfbdeaa8db`.
Both PL/pgSQL blocks use explicit `END;` terminators, consistent with existing migrations.

Standalone `.venv/bin/python scripts/check_l2_validation_schema.py` subsequently
returned **`ready: true`, `missing: []`**. Tables, named checks/uniqueness, index,
RLS and enabled lineage/immutability guards are verified in development. This
supersedes the initial engineering implementation's created-only status below;
installation on other targets remains unverified.

**Fifteen live synthetic checks passed**, exercising valid pinned draft/member,
freeze, initial reference, append-only final revision and completion; rejected
draft stage-skipping, frozen configuration changes, resampling/member/batch deletion,
initial-pointer replacement, completed final/batch modification, wrong body hash
and wrong review guideline. All fabricated articles, versions, annotation runs,
annotations, reviews and batches were rolled back through savepoints before the
migration commit. New validation tables contain zero real/synthetic batches.

Historical fingerprints were identical before/after: **536 articles, 536 extraction
versions, 14 annotation runs, 2,242 automated annotations and 303 human validations**.
Existing rows were held under short transaction SHARE locks during verification;
no original content, predictions or reviews were changed. The private installation
report and fingerprints remain ignored under `data/l2/schema-verification/`.
No model inference/retraining, real validation batch, real human decision,
independent performance result, production deployment or public Sheet change.
The existing full offline engineering suite remains 304 passing tests; this
follow-up verifies PostgreSQL installation/behavior rather than rerunning unchanged
Python/model semantics. Next: approved codebook/design and sufficient unseen pool,
then preview/freeze `L2-VALIDATION-V1` in the existing local app.

### L2 validation and protected reference workflow — 6 October 2026

**Engineering implemented; new migration created only. No real validation or
final-test batch created, no cloud database read/write in this task and no independent
performance measured.** Existing 324/324 coverage and historical outputs are retained;
the earlier real-run counts below are dated evidence, not a fresh database audit.

Implemented in the existing Flask Human Review:

* `annotations/validation_batches.py`: exact checksummed model/training provenance,
  seeded random and proportional publisher/language-metadata strata, diagnostic
  enrichment, membership digest and private pinned-reference evaluator math.
* `database/models.py`, `database/repositories/validation_batches.py` and
  `20261006_add_l2_validation_batches.sql`: additive batch/member tables, exact
  article/version/model snapshots, draft/frozen/in_review/completed lifecycle,
  initial/accepted human pointers, row/advisory locks and PostgreSQL immutability/
  lineage guards. The SQL was not installed or live behavior-tested. New tables
  use RLS; missing required tables/checks/guards/index/RLS fail readiness closed.
* `app/routes/validation.py`, existing review route integration, five templates
  and navigation: `/annotations/validation`, `/new`, `/<batch_id>` and
  `/<batch_id>/next`; blinded member review uses the existing exact-annotation URL
  with batch/member parameters. Preview, create, freeze, progress, next and
  completion retain current local/token/CSRF/trusted-identity/private-text security.
* Before the first human save, no machine label, probability, thresholds, weak
  answer or model evidence enters the batch template. Independent choice is blank.
  Initial pointers remain immutable across append-only revisions; completed final
  pointers stay pinned even if ordinary Human Review later changes. Development/
  diagnostic comparisons reveal only after the initial save; final-test batch
  feedback stays sealed and evaluation requires `--final-experiment`.
* Shared `AnnotationRepository.protected_membership()` automatically excludes
  frozen protected article/version/historical body hashes from reviewed-only,
  mixed-effective and weak-bootstrap exports and private priority selection.
  Existing manual manifests remain additive. Training CLI checks current protection
  against older exports before model loading. Selection fails closed if the new
  validation schema is missing; use the documented installation steps first.
* `scripts/check_l2_validation_schema.py` is a read-only preflight, never an
  installer. `scripts/evaluate_l2_validation.py` reads completed exact pinned
  predictions and accepted references, checks membership/lineage/probabilities and
  writes immutable deterministic private JSON/JSONL/hash manifests under `data/`.

Offline actual-provenance verification found **322 training articles, 322 versions
and 322 body hashes** for `l2-afroxlmr-dev-v1` / method
`l2-47035d92f81cd5240062610d`; training manifest SHA-256
`cdd8200674a103ab4e78c98254bb9e46c411cf82671827440c2b374474f2a132`.
Every one is training data. Independent selection excludes these and historical
hashes plus existing protected conflicts; requested sample size above unseen
support refuses with the actual available N. No live unseen-pool count was queried.
Diagnostic batches may inspect training data, clearly marked error analysis, and
never return representative accuracy/precision/recall/F1. Representative binary
metrics exclude human uncertainty/borderline and machine abstentions, reporting
support/abstention separately; no independent research score is asserted here.

**Executed verification:** targeted 82 tests (8.682 s), full offline suite with
explicit installed-artifact integration **304 passed, zero failures/skips**
(13.736 s). Twenty-nine new synthetic regressions cover deterministic allocation,
training IDs/versions/hashes, protected export paths, immutability, blind/final-test
feedback, exact pinning, trusted identity/local/CSRF, stale forms, progress,
unresolved policy, confusion math, deterministic private artifacts and old-export
training refusal. Python compilation, Markdown local-link/anchor/fence checks across seven maintained
guides, `git diff --check` and Git/private-exclusion checks passed. No collected
files are tracked; `.env`, datasets, evaluation outputs and model artifacts remain ignored. No model training or new persisted
inference was performed; installed-model integration uses synthetic input only.

**Operator handoff:** approve the codebook/design, confirm the target, run the
read-only schema preflight, apply the exact additive SQL once, verify readiness and
guards, then create/preview/freeze `L2-VALIDATION-V1` from sufficient unseen eligible
support. Review Next → independent labels → Complete → private evaluator:

```bash
.venv/bin/python scripts/evaluate_l2_validation.py \
  --batch L2-VALIDATION-V1 \
  --output-dir data/l2/evaluations/L2-VALIDATION-V1-v1
```

See [README operator steps](../../README.md#l2-validation-and-protected-reference)
and [annotations Section 22](../annotations.md#22-l2-validation-and-protected-reference-workflow).
Separate A/B reviewers/adjudication records, near-duplicate grouping, date strata,
AUC/calibration/subgroup metrics and reviewer-role isolation remain future work.
The ordinary machine-result pages are still accessible to the local operator;
blinding applies to the batch workflow. Do not freeze conflicting membership while
training is active; low-level training calls do not consult the protection database.
L0/L1 human-validation gates, unseen-positive support and independent performance
remain research blockers. No L3/L4, retraining, collection or public Sheet write.

Anonymous roadmap synchronization succeeded on 6 October 2026 using the repository
environment; all four CSVs were refreshed, without manual edits or writeback. The
Sheet now records 324/324 operational closure and research validation as current
priority. Its validation wording is planning/evidence state, not a claim that this
new engineering workflow was executed on real articles.

| Snapshot | Data rows | SHA-256 |
| --- | --- | --- |
| `roadmap.csv` | 32 | `76faef58b644722955abe29e354a6339904818f46dacb741af8f517c25de1dac` |
| `current_state.csv` | 11 | `b388b096dec57ed49c271c3a23f45390a5d191231e6bd88a8f8d4145a1e4dccc` |
| `stage_gates.csv` | 12 | `c9235a24a0b686f32b095cb02fe57d18d3fd9ef9fb16b2e844c65b1dabc61cfd` |
| `annotation_layers.csv` | 8 | `87e7ef4180187272c93a773f9f46a7464dc30df823f745f72c5739c9b20ef019` |

### Markdown alignment — 6 October 2026

Aligned all nine project-maintained Markdown guides to the executed 00:04 EAT L2
closure: 324/324 compatible predictions, 11/307/6, zero pending, installed and
behavior-tested development schema, unchanged prior history and 275 passing tests.
Corrected stale current summaries in AGENTS, deployment, collection handoff,
roadmap guidance and the annotation schema description. Older dated run/test
observations remain historical evidence. The three pinned upstream READMEs were
reviewed and preserved as source provenance.

Documented the proposed next implementation in
[annotations Section 17](../annotations.md#17-next-steps-future-work): agree the
codebook/sampling protocol, then add reproducible review batches, initially hidden
model output, separate adjudication and private progress/export reporting to the
existing local review workspace. These are planned capabilities. Training-article
reviews support error analysis; independent testing requires excluded training
articles/related duplicates and frozen reference membership.

This update changed Markdown only. No fresh roadmap synchronization, public Sheet
or CSV edits, code changes, database queries/writes, inference, review decisions,
training or evaluation were performed. Counts refer to the executed closure, not
a new live audit. The full-suite result remains the previously executed 275 passes;
validation for these documentation edits checks Markdown links/anchors, fences,
consistent current summaries and `git diff --check`.

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

### Project progress and documentation audit — 5 October 2026, 22:59 EAT

Fresh read-only aggregate checks reconfirmed 536 versions, complete L0 (519 valid /
17 needs_review / 0 invalid), complete eligible L1 v2 (324 kenya / 35 not_kenya /
160 ambiguous), and 300/324 transformer predictions (10/284/6), 24 pending.
Reviews: L0 zero, L1 one correction, weak L2 300 corrected + two confirmed
borderline; model L2 zero. Weak effective labels remain 10/312/2, with 22 unreviewed
binary machine results. Four required L2 schema objects remain absent.
No new training/inference, human writes, migration or production change was made.

The project is mapped explicitly in `docs/annotations.md` Section 1; Section 21
contains the actual model architecture and measured operational results. Review
found stale unconfigured/zero-prediction/weak-only statements in summary guides.
Updated README, AGENTS, AI_CONTEXT, annotation test/coverage/provenance sections,
collection handoff, deployment local-vs-production readiness, roadmap guide and
this log. Historical dated evidence is retained; current summaries supersede it.
The separate L2 performance report records reconfirmation without inventing metrics.
Fresh full-suite verification with the real installed artifact: **264 tests passed**,
zero failures/skips (9.646 seconds). Link/fence, snapshot hash and Git data-exclusion
checks passed; no `.env`, private records or model binaries are included.

Anonymous roadmap sync succeeded: all four exports unchanged. Snapshot L1 v2 and
human-review counts align, while exporter/first-model tasks still lag executed
code. The Sheet/CSVs were not manually changed. Final research gates remain open;
location baseline design is allowed by the plan after initial usable L2-positive
output, but independent final location validation is not established.

### Historical interrupted L2 run audit — 5 October 2026, 22:43 EAT

Read-only verification found **300 / 324 eligible transformer results (92.59%)**:
**10 gbv / 284 not_gbv / 6 borderline**, with **24 pending**. The recorded run
failed after one `OperationalError` and then `AnnotationLockLost`; it selected
536 versions, processed 489, saved 300 and skipped 188 on prerequisite gates.
These are partial-run counts. Stored duration is 1,093.565 seconds; timestamps
span 1,542.706 seconds; the later diagnosis links the discrepancy to idle sleep. Batched article-loading and
inference time is 227.627 seconds, not pure model latency.

At that historical audit, four required L2 objects were absent; the later closure above installed them.
No migration, retry or prediction write was performed by this documentation audit.
Training diagnostics, the bounded 20-record check, publisher coverage, schema
limits and evaluation requirements are documented in [L2 model performance](../l2_model_performance.md).
No independent held-out accuracy/F1 or calibration is established.

### Initial real AfroXLMR development model — 5 October 2026, 15:41 EAT

The updated roadmap was synchronized anonymously before implementation. Reviewed-only
and mixed-effective private exporters now resolve the latest exact-compatible human
revision before machine fallback. Unresolved reviews block fallback; human-confirmed
borderline remains excluded. Original annotations and reviews were not rewritten.
Explicit frozen-reference membership can exclude article/version IDs and historical
content hashes. No designated frozen human reference set was found or created.

Read-only final verification found 324 L1-Kenya eligible versions: original weak
labels **7 gbv / 15 not_gbv / 302 borderline**, current human overlay
**10 / 312 / 2**. Reviews comprise 300 corrections and two confirmed borderline;
22 binary weak results remain unreviewed. Counts describe article versions.

| Export | Pre-dedup binary | Post-dedup binary | gbv | not_gbv | Human confirmed binary | Human corrected | Weak unreviewed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| reviewed-only | 300 | 300 | 3 | 297 | 0 | 300 | 0 |
| mixed-effective | 322 | 322 | 10 | 312 | 0 | 300 | 22 |

Both exports exclude two confirmed borderline, zero unresolved reviews and zero
exact duplicate records. Reviewed-only additionally excludes 22 unreviewed records.
Exact duplicate conflicts are excluded; near-duplicate/syndication grouping remains
pending. Neither export is gold or a final evaluation corpus.

| Publisher | Reviewed-only | Mixed-effective |
| --- | ---: | ---: |
| Citizen | 137 | 141 |
| Kenyans.co.ke | 2 | 2 |
| Nation | 15 | 16 |
| Standard | 13 | 13 |
| Star | 10 | 14 |
| Taifa Leo | 76 | 89 |
| Tuko | 47 | 47 |

Language **metadata**, not independently validated language detection: reviewed-only
`en=87, en-KE=137, unknown=76`; mixed `en=92, en-KE=141, unknown=89`.
Private immutable JSONL/manifests are under `data/l2/reviewed-dev-v1/` and
`data/l2/mixed-dev-v1/`. Versions and record SHA-256s:

- `l2-reviewed-development-v1-c9ca121a586e68e1fab19ef2`:
  `c9ca121a586e68e1fab19ef2a5263aed38bbec85df5f4826a12b88db26e772cd`.
- `l2-mixed-development-v1-0bf75464737ca7d7816cbf86`:
  `0bf75464737ca7d7816cbf86cba7913360af57d35dcf18fa8d1a665ae2f0d32b`.

Lineage: L0 `l0-v1.0`, L1 `kenya_relevance_hybrid` /
`l1-v2.0-a39ff87099ee`, weak L2 `gbv_relevance_weak_supervision` /
`l2-ws-v1.0-32d7cc08144ebae3`. One historical review guideline is represented:
`docs/annotations.md-sha256:5db3e6322e7b722ca5c09a52e19e28a4fab05acdc02b062f320d3c81b81b0fa0`.
Later documentation edits do not change saved guideline lineage.

**Executed training:** `l2-afroxlmr-dev-v1` used all 322 mixed records, binary
`not_gbv=0, gbv=1`, deterministic TITLE/ARTICLE input and head truncation.
Base/tokenizer: [Davlan/afro-xlmr-base](https://huggingface.co/Davlan/afro-xlmr-base),
both pinned to `25f27299c247a6b73a767bd82d12444138b19337`.
Apple MPS was available/used; CUDA unavailable. Libraries: PyTorch 2.14.1,
Transformers 4.57.6, safetensors 0.8.0. AdamW, learning rate `2e-5`, three epochs,
batch two, 512 tokens, seed 42, weight decay 0.01; 483 optimizer steps.
Balanced cross entropy uses `weight_c=N/(2*n_c)`: gbv **16.1**, not_gbv
**0.5160256410256411**. Weighted per-example losses are summed and divided by
batch example count, preserving weighting in single-class/singleton minibatches.
`--class-weighting none` is supported; no oversampling/augmentation was used.

Training lasted **622.895 seconds** (10m23s), mean weighted loss
**0.5048725078**; epoch means **0.7354258622, 0.5244470051, 0.2547446561**.
Peak memory was not measured. These are training diagnostics, not accuracy.
Only **10 positives (3 human-reviewed)** exist: severe imbalance. No arbitrary
validation split was created. **NO RELIABLE INDEPENDENT DEVELOPMENT VALIDATION
METRICS DUE TO LIMITED POSITIVE CLASS SUPPORT. NO FINAL HELD-OUT HUMAN REFERENCE
SET IS CURRENTLY FROZEN.** No precision/recall/F1/AUC or calibration was reported.

Private ignored artifact: `models/artifacts/l2-afroxlmr-dev-v1/`, containing
safetensors, configuration, tokenizer and `model_manifest.json`. Its manifest
records all training/provenance counts, library versions and individual file hashes.
Code commit `0fdb389e67e9e9d1601ff2bb8cd435f667a78d7e`, dirty worktree true;
commit alone does not reproduce these changes. Manifest SHA-256:
`c3f63ed005a511bf690b2ec5219976a699d0f15965eadf64d6d97d4fe6ee47d5`.
Weights SHA-256:
`657b1aa6dc576c5d9ff9524d1c779836ceb72d226f504cd33d1c493d73e34be7`.

Offline reload validated all checksums and binary order with Hub access disabled,
`local_files_only=True`, `trust_remote_code=False`, safetensors, `eval()` and
`inference_mode()`. Existing **unvalidated engineering thresholds** remain
positive 0.8 / negative 0.2; confidence is `uncalibrated_softmax_probability`.
A read-only bounded engineering check processed **20 real versions across seven
publishers**, failed **0**, output **gbv 0 / not_gbv 19 / borderline 1**.
Mean inference 120.482 ms, median 81.057 ms; load 3.449 s. This is not evaluation.
Private reports and 20 review-priority rows are under
`data/l2/afroxlmr-dev-v1-check/`; no automatic human corrections were made.

Ignored local `.env` now configures this artifact and batch two. Method identity
is `l2-47035d92f81cd5240062610d`; final local readback reports model ready.
At this historical milestone, the database lacked all four required L2 schema objects: label constraint,
prerequisite constraint, method/dependency index and L1-Kenya prerequisite trigger
from `20261005_add_l2_annotations.sql`. The migration was **not installed** by
this task. **Zero model predictions were written; all 324 remain DB-pending.**
No production configuration or public Sheet was changed.

Full suite including explicit installed-model integration: **264 tests passed,
zero failures/skips**. Ordinary unit tests use fakes and do not download AfroXLMR.
New tests cover latest revisions/provenance, unresolved exclusion, compatible
prerequisites, reference/historical-hash protection, duplicates, manifest checks,
weighted training and schema readiness. `git diff --check` passed; datasets,
caches, weights and `.env` remain ignored and untracked.

Before thesis evaluation: approve the versioned codebook, expand independently
reviewed positives/source-language coverage, validate L0/L1, group near duplicates,
freeze independent reference membership, agree defensible evaluation/calibration
protocols and acceptance thresholds, and resolve the DB migration through the
operator workflow before prediction writes. L2 research gates remain open.

### Historical human-review and initial-model readiness — 5 October 2026, 14:52 EAT

Read-only development Supabase verification after the user-authorized review writes:

| Current compatible L2 weak view | gbv | not_gbv | borderline | Total |
| --- | ---: | ---: | ---: | ---: |
| Original machine labels | 7 | 15 | 302 | 324 |
| Latest human decisions overlaid on machine labels | 10 | 312 | 2 | 324 |
| Human-reviewed records only | 3 | 297 | 2 | 302 |
| Not reviewed | 7 | 15 | 0 | 22 |

All 302 originally machine-borderline results have saved human reviews: 300
corrected and 2 confirmed borderline. The user reported completing human review.
The requested bulk decisions were appended as 74 Taifa Leo borderline → `not_gbv`
corrections, followed by 223 remaining borderline → `not_gbv` corrections, excluding
latest human-confirmed borderline. Three other current corrections are to `gbv`.
Machine outputs, exact extraction/prerequisite lineage and prior review history
were preserved. Bulk recording is not an automatic negative rule for future
borderline results, and the audit did not independently assess article content.

The result-count fix is implemented locally: current L2 labels/counts/filters and
cohort navigation use the latest human decisions; original automation remains
inspectable with `label_basis=machine`. Weak/model methods stay separate. Counts
honor review-status filters; `not_reviewed` hides saved corrections, and the page
now explains that filter scope. No machine probability is recalculated.

**Historical training handoff (superseded by the executed model above).** At this audit the exporter in
`annotations/l2_training.py` reads original weak labels, ignores human corrections
and excludes machine-borderline rows. The trainer accepts weak-bootstrap manifests
only. Add explicit reviewed/mixed label export and compatible manifest validation
before using the saved decisions for fitting. The two confirmed borderline records
remain excluded from binary development data. Choose and record reviewed-only
(at most 3 positive/297 negative) or mixed development membership (at most
10 positive/312 negative) before deduplication and splitting. Mark machine-only
labels explicitly; do not describe the combined 322 binary labels as all reviewed.

The [annotation specification](../annotations.md) now documents review evidence,
working label meanings, unresolved codebook approval, export provenance,
duplicate grouping, independent held-out membership and evaluation requirements.
A final approved inclusion/exclusion codebook, dataset freeze/splits, numeric
acceptance thresholds and independently measured performance remain outstanding.
Only 10 positives exist in the mixed pool, and only 3 are human-reviewed; class
support after splitting requires explicit assessment before training/evaluation.
L0/L1 validation gates remain open. The earlier L2 annotation-migration gap is
historical inspection evidence; this earlier count audit did not install or recheck schema.
The primary L2 method was verified as `l2-model-unconfigured`; no training or
inference run was initiated by this documentation update.

**Planning synchronization:** `python3 scripts/sync_roadmap.py` could not run with
the system Python because `requests` was unavailable. The project-venv run then
encountered sandbox network restrictions; an approved network-enabled rerun
succeeded and refreshed all four CSV snapshots anonymously, without Google
credentials. The refreshed Sheet now records L1 v2/L2 infrastructure and supports
an initial AfroXLMR on current usable data, iterative corpus growth toward ≥5,000,
and an independent held-out human reference subset. Its original weak counts
7/15/302 remain consistent with preserved machine outputs. No Sheet rows or CSV
values were manually edited, and research exit gates were not declared complete.

**Engineering validation:** the earlier result-count change passed the full offline
suite: 251 tests run, 250 passed, one optional installed-model test skipped. The
subsequent review-filter notice passed 19 targeted L2 UI/review tests. Those tests
use synthetic data and do not validate research labels. This documentation-only
update checks Markdown structure/local links and `git diff --check`; it does not
rerun model or collection workflows. Private article content, reviewer identities,
review-row identifiers and credentials are omitted from this log.

### Historical verified development state — 5 October 2026, 12:44 EAT

**Historical pre-review audit; use the 14:52 EAT snapshot above for current L2 review state and planning alignment.**

Read-only aggregate queries found:

| Output | Current compatible coverage | Labels / readiness |
| --- | ---: | --- |
| Article versions | 536 | Unvalidated research candidates |
| L0 | 536 / 536 | valid 519; needs_review 17; invalid 0 |
| L1 v2 | 519 / 519 L0-valid | kenya 324; not_kenya 35; ambiguous 160 |
| L2 weak bootstrap | 324 / 324 L1-Kenya | gbv 7; not_gbv 15; borderline 302; weak pending 0 |
| L2 primary model | 0 / 324 eligible | `l2-model-unconfigured`; model pending 324 |
| Current human reviews | L0 0; L1 1; L2 weak 0; L2 model 0 | Validation sample/metrics incomplete |

Current L0 identity is `l0-v1.0`; L1 is `l1-v2.0-a39ff87099ee`. Automated
weak labels are provisional and do not count as model predictions or reference
labels. Aggregate review counts include genuine saved decisions only; this audit
created none. The readback establishes coverage, not correctness or calibration.

**Schema prerequisite still missing:** the expected named label/prerequisite checks,
identity index and enabled prerequisite trigger from `20261005_add_l2_annotations.sql`
were absent during inspection. Existing weak rows do not establish installation.
The human-validation table and L2 human-review extension are installed. Apply the
L2 annotation migration to the intended database before further automated L2 writes; this
documentation audit performed no schema or annotation mutations.

At this historical 12:44 EAT audit, the Sheet described L2 as planned and recorded
historical L1 v1 outputs; the latest synchronized planning mismatch is noted above.
Repository code implements L2 infrastructure and local review, with current weak
coverage as above. This mismatch is explicit; public planning rows/CSVs and
research gates were not manually changed. The older dated sections below remain
historical execution evidence.

The Sheet's 407-record trial count is a planning snapshot. Live Supabase queries
on **3 October 2026 (Africa/Nairobi)** found **536 articles / 536 article versions**.
The user authorized L0 across all 536 after the successful 20-version L0/L1 trial,
then explicitly authorized L1 on all 499 remaining L0-valid versions. The 17 L0
review cases remain gated. Exact selected-version UUIDs are recorded privately
in each run's configuration.

## Completed

* L2 operational closure: installed/behavior-tested schema, scoped macOS sleep
  prevention, fail-closed ownership checks and pending-only resume; 324/324 current
  compatible model results, zero pending, all prior row fingerprints unchanged.

* Collection retained: seven publisher parsers, bounded/retrospective collectors,
  private GCS/Supabase lineage, local import and run/scan monitoring. No scraper changes.
* Roadmap sync ran first; all four snapshots were inspected. The Sheet was not changed.
* One shared `run_annotation_pipeline(...)` for CLI, bounded UI and future automation.
  Collection and annotation remain decoupled.
* Additive `annotation_runs` / `automated_annotations` migration applied to the
  configured development Supabase database; existing collection tables preserved.
* L0 deterministic quality/provenance rules (`extraction_quality_rules`, `l0-v1.0`),
  hard/soft reasons, valid/review/invalid labels and NULL confidence. Processed JSON
  uses its recorded GCS generation and is compared with extraction lineage.
* L1 versioned geographic/institution evidence scorer (current expanded v2 resource,
  historical v1 retained), conservative foreign/mixed/ambiguous handling,
  structured evidence and normalized confidence. Publisher identity supplies no score.
* L1 requires the exact current valid compatible L0. Invalid/review L0 cannot enter
  L1; L1-only execution does not implicitly execute L0.
* Append-only history, pending-only processing, force, parameter method identities,
  latest-compatible queries, advisory locking, failure isolation, per-version
  checkpoints/counters and structured secret-safe logs.
* Flask summary, run list/detail, filtered L0/L1/L2 results and article history.
  Opt-in token/CSRF trigger is disabled by default and capped at 20 versions.
* Real bounded 20-version trial persisted both layers with zero failures; full L0
  subsequently covered all 536 versions. Default repeats added no duplicate decisions.
* Authorized full L1 completed: 499 new decisions, 17 gated review-case skips,
  zero failures and CLI exit 0. All 519 L0-valid versions now have L1 decisions.
* Authorized v2 reprocessing preserved v1 history; current v2 eligibility is 324 Kenya
  versions. All 324 have compatible L2 weak labels and now compatible model results:
  11 gbv / 307 not_gbv / 6 borderline, zero pending after operational closure.
* L2 weak supervision, private development export, training CLI, checksummed offline
  model inference and bounded synthetic smoke are implemented. Real initial
  development fine-tuning is executed; independent performance is not established.
* Protected local L0/L1/L2 Human Review, direct unlock, separate append-only decisions,
  revisions/conflict handling and method-separated status/filter/navigation are implemented.
* README, AGENTS, AI_CONTEXT, annotation specification and deployment notes updated.
* Follow-up roadmap sync found all snapshots current; all 152 existing tests passed.
  Existing-result reads were subsequently batched per locked cohort to remove
  per-article lookups, with forced dependency/version behavior unchanged.

## In Progress

Automated implementation and authorized L0/L1 execution are complete. Human
review of all 302 originally borderline L2 weak results is recorded; 22 originally
binary weak results remain unreviewed. Independent sampled validation, codebook
finalization and protected independent evaluation remain pending. Reviewed/mixed
export and first-model weighted training are complete. Readiness gates
have not been passed through automation or review coverage alone.

## Next

1. Inspect L0 anomalies by publisher and resolve extraction defects through versioned
   reprocessing, retaining flagged records and original evidence.
2. Preserve exact dynamically queried membership for any corpus expansion or pilot;
   the old 407-record planning snapshot is already superseded by 536 versions.
3. Review initial rules/gazetteer and agree error thresholds, sample sizes and an
   uncertainty/stratification protocol. Engineering thresholds are not calibrated.
4. Inspect L1 ambiguity, evidence and source/language coverage over the eligible corpus.
5. Keep installed-schema/lease safeguards enabled; completed model coverage does
   not close independent research-validation gates.
6. Plan structured human validation: reproducible source/language/label batches,
   initially hidden model output, separate adjudication and private progress/export
   reporting. Agree codebook/sampling first; these additions are not implemented.
7. Under a later authorized research milestone, store independent reference labels
   separately, exclude training articles/related duplicates, freeze membership and report defensible
   accuracy/F1, false-pass/false-fail, calibration and subgroup evidence before
   claiming research exit-gate completion.

L2 infrastructure, reviewed/mixed exports and the initial real development model
are implemented. Full eligible inference and installed L2 schema readiness are
complete. Independent model validation, L3–L5, NER, geocoding and mapping remain pending. Automated outputs
are not gold labels; execution alone does not satisfy sampled-validation gates.

## Blockers / Limitations

* Historical bounded trial/full L0 had no infrastructure blocker. The L2
  schema/idle-sleep interruption was resolved in the closure above; general network
  interruptions still fail closed and require operator pending-only resume.
* Human-reference data and agreed numeric acceptance thresholds are absent.
  L0/L1 quality, coverage and confidence have not been independently validated.
* Raw references are checked without per-version raw-object existence reads.
  Processed objects are fetched for body evaluation and generation lineage.
* Lexical gazetteer is bounded and does not resolve incident locations. Mixed
  evidence is deliberately ambiguous; language metadata remains unvalidated.
* The synchronous 20-version trial took about 140 seconds. Local UI execution
  needs `gunicorn --timeout 600`; remote UI remains disabled until hosting
  deadlines and trusted HTTPS are configured. Token/CSRF protection is not a
  full user/reviewer authentication system.
* The original full-run CLI exited 2 after its completed database checkpoint because
  its long-idle lock connection failed during unlock. All 516 new results were saved.
  Annotation-specific locking now uses autocommit and backend-identity heartbeats,
  fails closed on lost leases, and logs cleanup disconnects without hiding completed
  results. Direct/session-pooler connections are required; transaction pooling is rejected.
  Existing collection code was not changed. The long full run was not force-repeated.

## Last Roadmap Sync

Latest anonymous synchronization succeeded on **5 October 2026 (Africa/Nairobi)**
during operational closure; all four exports were refreshed. The
latest refreshed Sheet records the trained model and 300/324 pre-closure coverage;
repository closure now records 324/324. Final research validation remains pending
in both accounts; the public Sheet was not modified by this task. Required headers
matched and no canonical planning rows or synchronized CSVs were manually edited.

| Snapshot | Planning rows | SHA-256 |
| --- | ---: | --- |
| `roadmap.csv` | 31 | `b7bd48882a8d0b65586b90d56da44a479841550ad4dd16b2904236defc8bc14f` |
| `current_state.csv` | 10 | `7b21f8f55a132957bdc907183279dbab97991a6eb62e8719959298b3d8849bd5` |
| `stage_gates.csv` | 12 | `ad7adbe7c7c3d6ff369bda135348d7ee0a7bcb9dfda3669cc76ea16b22847288` |
| `annotation_layers.csv` | 8 | `6a1f14954fce9b454e7bd6d1c8b2f44aa747a94e946f053f60a0dcf56b6b8481` |

## Relevant Code / Migrations

* `annotations/{service,l0,l1,schemas}.py`, `annotations/resources/kenya_v1.json`.
* `annotations/{geography,l2,l2_config,l2_datasets,l2_training,l2_readiness,l2_weak_supervision,validation}.py`,
  expanded `kenya_v2.json` and provisional `gbv_relevance_v1.json` resources.
* `database/models.py`, `database/repositories/annotations.py`.
* `migrations/20261003_add_automated_annotations.sql` — applied to development;
  other deployments must apply it separately.
* `scripts/run_annotations.py` — layers, limit, UUID filters, force, JSON summary.
* `scripts/{prepare_l2_training_data,train_l2_classifier,check_l2_model,smoke_l2}.py` — private
  development exports, training and synthetic architecture verification.
* `database/repositories/human_validations.py` and
  `20261004_add_human_validations.sql` / `20261005_add_l2_human_validations.sql`
  — implemented review storage and installed development extension.
* `20261005_add_l2_annotations.sql` — installed and behavior-tested in development
  during operational closure. Verify each other target database separately.
* `tests/test_l2_operational_completion.py` — 11 schema, sleep, lease, diagnostic
  and pending-only history-preservation regressions.
* `app/services/annotation_service.py`, `app/routes/annotations.py`, annotation
  templates, article detail/history, navigation and opt-in app configuration.
* `storage/gcs.py` — optional generation-pinned JSON reads.
* `docs/annotations.md` — architecture, initial specification, CLI/UI, limitations.
* Existing roadmap/import/collection scripts and ingestion migrations retained.

## Test Status

Latest full suite including installed-model integration on **5 October 2026**:
**275 passed, zero failures/skips**. L2 review verification and
synthetic smoke details appear in the dated entries below. Operational closure
ran the existing artifact pending-only after schema/test verification; no collection,
training or human-decision changes were performed.

### Historical L0/L1 milestone verification

* `.venv/bin/python -m unittest discover -s tests -q`: **155 tests passed** —
  previous 108 plus 47 annotation tests, with publisher/HTTP calls mocked.
* Rules: L0 required checks/severity/determinism/dates/malformed refs; L1 all 47
  counties, foreign/mixed/weak evidence, case/boundaries and publisher independence.
* Pipeline: persistence, prerequisites/gating, counters/status, failure isolation,
  pending-only repeats, force/history and shared CLI bridge.
* Batch regressions confirm no per-article existing-result queries in the runner,
  one compatible-current query per cohort and no query for an empty selection.
* L1 integrity regression refuses missing/mismatched processed inputs after a
  valid L0, retaining the original gate/result and recording a safe failure.
* Lock regressions cover autocommit, disconnect cleanup, changed/lost backend,
  fail-closed processing/counters and transaction-pooler rejection.
* Actual synthetic SQL window queries verify latest L0 gating, history preservation,
  custom/default method separation and compatible L1 resolution.
* GCS tests verify pinned/legacy reads, missing objects and surfaced failures.
* UI tests cover routes, bounded POST, CSRF, replay, disabled/short secrets, Unicode
  tokens, local HTTP and remote HTTPS behavior.
* Live Flask test-client GETs returned HTTP 200 for existing `/`, `/runs`,
  `/articles`, article detail, all annotation pages, trial run detail and filtered
  L0 results. Disabled POST returned 403.
* Real protected UI POST returned 303, completed run detail returned 200 and stale
  form submission returned 403. Temporary in-memory secrets were not saved to config.
  Run `48d175d7-14d1-4040-a610-32339157d412` selected zero pending versions; result
  count remained **556** before/after.
* Live repeat CLI run `3a3e9e4a-579e-4f40-9882-290225a80297` completed, selected
  zero pending L0 versions and added no annotation results.
* Final live checks passed: lock heartbeat/backend identity, rejection of concurrent
  acquisition and successful reacquisition after release. All ten collection/
  annotation GET checks returned 200. L0-milestone aggregate readback confirmed 536 L0,
  20 L1, zero pending L0, 499 pending L1 and zero duplicate method groups.
* `git diff --check` passed; `git ls-files data` returned no collected artifacts.
* Full L1 CLI exited 0 after approximately 31.7 minutes, verifying long-run lock
  cleanup on the updated path. Final readback confirmed 536 L0 + 519 L1 rows,
  no pending eligible work and no duplicate method groups. Combined pending-only
  repeat `f9c40435-75c6-497c-b2fd-8ded2fdba56c` selected zero records and completed.

## Trial Run Results

### Bounded L0 + L1 (actual)

Command: `.venv/bin/python scripts/run_annotations.py --layer l0,l1 --limit 20`.
Run: `663530f6-e398-4195-8c24-9d70dc8ff7f5`.
Status: **completed**. Selected/processed/successful versions: **20 / 20 / 20**;
skipped **0**; failures **0**. Duration: **139,512.69 ms**.

| Layer | Observed labels | Gated skips | Failures |
| --- | --- | ---: | ---: |
| L0 | valid **20**, needs_review **0**, invalid **0** | 0 | 0 |
| L1 | kenya **14**, not_kenya **3**, ambiguous **3** | 0 | 0 |

Stable creation/UUID-order selection makes this an engineering smoke test, not
a random/stratified research-validation sample. Labels came from real persisted
records; no human correctness claim is made.

### Authorized full-scope L0

Command: `.venv/bin/python scripts/run_annotations.py --layer l0`.
Run: `cf86ffad-1e7e-4e70-8beb-45e2be8c0d46`.
Selected **516** remaining versions; earlier **20** L0 results preserved.
Persisted status: **completed**; 516 processed/successful, 0 failed, 0 skipped.
New labels: valid **499**, needs_review **17**, invalid **0**.
Duration recorded at completion: **2,009,473.34 ms** (about 33.5 minutes).
The subsequent lock-release error affected CLI exit/summary output, not saved results;
see the fix and validation above.

| Layer after L0 milestone | Annotated | Labels | Pending |
| --- | ---: | --- | ---: |
| L0 | **536** | valid **519**, needs_review **17**, invalid **0** | **0** |
| L1 | **20** | kenya **14**, not_kenya **3**, ambiguous **3** | **499** L0-valid versions |

The 17 review cases are **12 missing publication dates** (Standard 4, Taifa Leo 8)
and **5 short bodies** (The Star). No invalid or infrastructure-failed versions were
observed. All processed-object generations were present; method-group duplicates
were absent in database readback. These engineering checks do not establish that
every extraction or relevance decision is correct. No article content was deleted,
source metadata overwritten, or human/reference label invented.

### Authorized full-scope L1

Command: `.venv/bin/python scripts/run_annotations.py --layer l1`.
Run: `72e7ec86-90c8-4610-b48d-a43a26567f43`.
Scope: all remaining **499 L0-valid versions**, preserving the 20 trial decisions.
Actual status: **completed**, CLI exit **0**. Selected/processed 516 versions;
successfully annotated **499**; **17** skipped because L0 needs_review; **0** failed.
Recorded duration: **1,901,816.68 ms** (about 31.7 minutes).

| New L1 label | Observed count |
| --- | ---: |
| kenya | **293** |
| not_kenya | **70** |
| ambiguous | **136** |

### Historical v1 full-corpus coverage (verified after full L1 on 3 October)

| Layer | Current decisions | Label counts | Pending eligible versions |
| --- | ---: | --- | ---: |
| L0 | **536** | valid **519**, needs_review **17**, invalid **0** | **0** |
| L1 | **519** | kenya **307**, not_kenya **73**, ambiguous **139** | **0** |

Supabase contains **1,055** automated rows, no duplicate version/layer/method
groups and complete processed-generation metadata. The 17 quality-review versions
have no L1 result. These are automated outputs requiring sampled human validation.
The repeated combined pending-only command selected zero versions, persisted no
new annotation decisions and completed with exit 0.

## L1 v2 geographic-resource enhancement — 4 October 2026

The roadmap item **Implement automated L1 Kenya-relevance annotation** now also
has an implemented deterministic geographic-resource enhancement. This is an
engineering extension of existing L1, not completion of the sampled-validation
exit gate or the Sheet's broader NER/classifier plans. Anonymous sync succeeded
on 4 October before work: Roadmap, Current State and Stage Gates refreshed;
Annotation Layers was current. All four tabs and AI_CONTEXT were inspected.
Canonical Sheet planning rows were not edited by this task.

* Inspected all three requested repositories, root LICENSE/README/data, and the
  Tigawanna ward/counties/constituency GeoJSON and source download script.
  Pinned commits, repository licenses, documented source claims and file SHA-256s
  accompany the vendored public geographic inputs. Underlying official editions,
  data licensing and code authority remain unverified.
* `scripts/build_kenya_gazetteer.py` reproducibly builds/verifies
  `kenya-gazetteer-v2.0`: 47 counties, 307 sub-counties, 290 constituencies,
  1,448 wards, 916 localities, 1,827 areas and 36 retained towns. Two area duplicates
  were reconciled; one missing Rosslyn locality parent is null/flagged. References
  disagree (Tigawanna 1,439 wards; Alvinchesaro 45 county keys); full computed
  discrepancy tuples and alias collisions are recorded rather than silently merged.
* Cached alias indexes/token trie, longest lexical matches and canonical-name
  deduplication provide one place observation per expression/name. Ward parents
  add metadata rather than score. Shared-name/common-word/surname/cross-border
  and unresolved-parent ambiguity is explicit. Country/institution/foreign logic,
  all weights/caps/thresholds/confidence formulas and label vocabulary are unchanged.
* Default effective method is `l1-v2.0-a39ff87099ee`, with resource SHA-256 included
  in compatible identity. Changed weights append their own digest. V1 resource
  remains unchanged, executable and selectable via `--l1-gazetteer v1`; v1 database
  decisions remain historical. No database migration was introduced.
* Flask result/history pages show structured geographic details and still render
  v1. No human-review, L2/L4, NER, geocoding, live scoring APIs, polling stations
  or new dependency was implemented.
* Deterministic rebuild check and **171 offline tests passed**. Added integrity,
  matching, hierarchy/score, ambiguity, cache, version/SQL compatibility, pipeline
  history/pending and Flask v1/v2 rendering tests. `git diff --check` passed.
* Read-only final comparison on 20 existing L0-valid/v1-result versions succeeded:
  kenya → kenya 14; ambiguous → ambiguous 3; not_kenya → ambiguous 3; other six
  transitions zero. Kenya scores changed on 11, foreign scores on zero and matched
  place sets on 18. Mean Kenya score 6.825 → 8.775; foreign 1.5 → 1.5.
  Private per-version report remains ignored under `data/trials/processed/`.
  Selection is stable creation/UUID order, not stratified/reference validation.
* Local loading time: v1 0.248 ms/v2 21.792 ms. Mean evaluation: 9.5848/4.4143 ms;
  medians 8.5655/4.0519 ms, excluding cloud reads/writes. Single smoke measurements
  establish neither production latency nor accuracy improvement.
* No annotation run/results were written by comparison, and no full-corpus v2
  reannotation occurred. The current monitor now uses v2 compatibility; historical
  v1 completion does not imply v2 completion. Review changed evidence/weak-word
  ambiguity before approving full v2 reannotation. Sampled human/reference
  validation and numeric research acceptance thresholds remain pending.
* `docs/annotations.md`, `docs/AI_CONTEXT.md`, README and this log describe the
  implemented resource/build/versioning/CLI/evidence/performance and limitations.
  Existing user edits to annotations documentation were preserved.


## Authorized forced full L1 v2 run — 4 October 2026

Following the bounded enhancement comparison, the user explicitly requested a
full rerun using force and v2. Executed:

```bash
.venv/bin/python scripts/run_annotations.py --layer l1 --l1-gazetteer v2 --force
```

* Run `437f091c-436c-4f40-8d29-62904f382354`, method `l1-v2.0-a39ff87099ee`:
  **completed**, CLI exit **0**, 536 selected/processed, **519 fresh decisions**,
  **17 current-L0-review gated skips**, **0 failures**. Duration
  **1,238,193.64 ms** (about 20 minutes 38 seconds). L0 was not rerun.
* Final read-only database check confirms current v2 Kenya **324**, not Kenya
  **35**, ambiguous **160**, with **zero eligible v2 pending**.
* All **519 historical v1 rows** have an identical complete-row fingerprint
  before/after the run. Existing 20 v2 trial rows were retained: 539 v2 historical
  rows now coexist with 519 v1 rows and 536 L0 rows (1,594 automated rows total).
  Force intentionally appends same-method history; compatible-current queries
  resolve 519 latest v2 decisions linked to their current valid L0 prerequisites.
* Full stored-label comparison: Kenya→Kenya **307**; not Kenya→not Kenya **35**;
  ambiguous→ambiguous **122**; ambiguous→Kenya **17**;
  not Kenya→ambiguous **38**; all other four transitions **0**.
* Private run log and initial/final verification artifacts remain under ignored
  `data/trials/processed/l1-v2-force-*`. No collected data is tracked/published.
* README, annotation reference and AI_CONTEXT now reflect executed v2 coverage.
  Public Sheet snapshots were not manually edited. Full automation does not
  establish accuracy or complete the sampled-validation research exit gate.


## Annotation inspection and protected local Human Review — 4 October 2026

Anonymous roadmap synchronization succeeded for all four tabs before this work;
all snapshots, AGENTS.md, AI_CONTEXT and the annotation reference were inspected.
This implements the engineering workflow supporting sampled human validation. It
**does not mark Human Validation or the sampled-validation exit gate achieved**.
Canonical Sheet rows were not edited. No sampling, calibration, automatic human
reviews, downstream layers or model training were added.

* All L0/L1 total and label cards link to paginated results using Flask URLs, with
  hover/focus states and emphasis on L0 needs-review / L1 ambiguous. Label/source/
  review-status filters are validated; lists show machine evidence and human status.
* GET/POST `/annotations/review/<uuid:annotation_id>` combines article metadata,
  exact extraction, machine/run evidence and human review/history. All labels and
  historical results remain reviewable. Article history links both ways. Previous,
  Next, Back and Save & Next retain cohort filters/page, including status-filter
  pagination when saving removes an item from the cohort.
* Full article text is fetched only for unlocked local sessions, using the existing
  generation-pinned GCS loader and extraction lineage/hash verification. Bodies and
  notes are escaped; private no-store responses and safe error-type logs are used.
* Additive `20261004_add_human_validations.sql` creates separate exact-lineage human
  records with controlled decisions/labels, machine snapshots, configured reviewer/
  guideline identity, reasons/notes, timestamps and append-only supersession history.
  Unique chain indexes, stale-form checks and machine-row locking protect revisions.
  Current review status is deterministic; forced/new machine rows do not inherit it.
* Human Review is disabled by default, CSRF protected, direct-localhost only and
  expires after 30 minutes. It requires a distinct review token, Flask secret,
  actual configured reviewer identity and guideline version. Remote/proxied review
  is blocked pending proper authenticated reviewer accounts and authorization.
* **190 offline tests passed**, including 19 new executed repository/Flask review
  tests. Dashboard links, filtering/pagination, all labels, safe pinned body loading,
  v1/v2 evidence, separate confirms/corrections, unchanged machine data, history,
  stale forms, CSRF, access restrictions, Save & Next and unavailable storage were
  exercised. Existing collection/annotation tests remain passing.
* Migration was applied to the configured development Supabase database. Before/
  after complete-row fingerprints confirm all **1,594 automated annotation rows
  unchanged**; human table row-level security is enabled and **zero human rows** exist.
  Current machine counts: L0 valid **519**, needs-review **17**, invalid **0**;
  L1 v2 Kenya **324**, not Kenya **35**, ambiguous **160**. Human pending: L0 **536**,
  L1 **519**; priority progress **0/17** and **0/160**. No human decision was fabricated.
* L0/L1 scorer SHA-256s exactly match the pre-work snapshot. README, `.env.example`,
  annotation reference and AI_CONTEXT document local setup, schema, security and
  remaining research work. Public roadmap snapshots contain no private review data.

## L2 GBV relevance infrastructure — 5 October 2026

The user explicitly authorized L2 implementation and bounded local engineering
smokes, while forbidding full-corpus reannotation, expensive/full training,
production deployment and destructive data changes. Anonymous roadmap sync
succeeded for all four tabs and found snapshots current. Required architecture,
operator, annotation and research documents were inspected. No public Sheet rows
were edited; existing unrelated workspace changes were preserved.

**Completed engineering item: automated L2 implementation infrastructure. The L2
research stage/gate remains open.** L0/L1 sampled-validation evidence and agreed
numeric research thresholds are still missing. Code availability does not supply
validated labels or authority to skip those gates.

* Added L2 labels, an additive migration with same-version L1 Kenya prerequisite
  checks/trigger and a method/dependency index. The migration is provided but
  **not applied to any cloud database in this task**. Historical migrations and
  L0/L1 rule/scoring/gazetteer semantics were not changed by this task.
* Shared CLI/service supports L2-only and ordered combined layers. Compatibility
  derives the actual configured L1 version; it does not fix v1 or a corpus count.
  Exact current L1 method/label/prerequisite and L2 method/version/parent are
  matched before ranking. New L1 makes previous L2 historical. Pending-only,
  force/history, cooperative locks, private input verification, per-version
  failures and safe run summaries/logs are retained.
* Versioned provisional weak-supervision resource and independent labeling
  functions preserve votes, lexical evidence, counts and rule/aggregation identity.
  Strong consistent positive/negative signals can yield binary bootstrap labels;
  conflict/weakness/absence retains borderline. Publisher identity supplies no
  vote. English/Swahili coverage is bounded; Sheng-specific terms remain empty
  pending linguistic validation. No complete approved inclusion/exclusion
  codebook was found, so rules are explicitly provisional, not a new thesis definition.
* Bootstrap labels use `gbv_relevance_weak_supervision`; Transformer predictions
  use `afroxlmr_gbv_relevance`. Weak labels cannot satisfy current-model queries.
  A private deterministic builder exports existing exact-compatible binary weak
  labels and lineage, excludes borderline/duplicate body hashes, verifies stored
  objects and creates a checksummed development manifest. It does not export
  unnecessary URL/author metadata or create human/reference labels.
* Separate AfroXLMR-compatible training supports configured base/revision,
  development dataset/version, CPU/MPS/CUDA, seeds, batch size, epochs, learning
  rate, maximum length and bounded steps. It reports bootstrap training loss only.
  Artifacts preserve reproducibility metadata, label order, tokenizer, dataset,
  weak method, installed-file hashes and provisional threshold status.
* Installed-artifact inference is offline-only, caches model/tokenizer, uses eval/
  inference mode, binary GBV probability and configurable thresholds. L2-only
  service batches verified eligible inputs and isolates batch/member failures.
  Missing/invalid/untrained artifacts fail clearly; there is no weak/network fallback.
  `0.8/0.2` are **UNVALIDATED ENGINEERING THRESHOLDS**, not calibrated research values.
* Flask adds dynamic clickable model/eligible/pending/label coverage, current
  model and explicit weak views, filters/pagination, L1 links, safe read-only
  evidence/detail and article history. Full text uses existing protected local
  access. No L2 human-review writes/interface or L3–L5 implementation was added.
* README, `.env.example`, AI_CONTEXT and the annotation reference document local
  dependencies, commands, migration/configuration, private artifact storage,
  method identity, confidence terminology and research limitations.

### Bounded executed synthetic smoke

Installed optional ML development dependencies locally, then ran:

```bash
.venv/bin/python scripts/smoke_l2.py --output-dir data/l2/synthetic-smoke-20261005
```

The smoke creates a **4,018-parameter random tiny XLM-R architecture** and a
synthetic WordLevel tokenizer, uses four fabricated English/Swahili examples with
both weak binary classes, performs **two CPU training steps**, saves a manifest/
safetensors/tokenizer artifact and reloads it for a four-input batch. It downloaded
**no model/tokenizer artifact** and accessed **no real corpus or cloud database**.
All four model outputs were borderline, consistent with an unvalidated tiny smoke
rather than a research-trained classifier. The artifact is named
`synthetic-smoke-not-research-v1` and was not configured as the primary L2 model.

| Separate local smoke measurement | Time |
| --- | ---: |
| Weak supervision, four synthetic inputs | 2.180 ms |
| Two tiny CPU training steps plus artifact save | 81.878 ms |
| Installed tiny model/tokenizer load | 4.938 ms |
| Tiny Transformer batch inference, four inputs | 1.625 ms |

These one-shot measurements exclude library import/startup and cloud I/O. The
1.625 ms number is **not AfroXLMR-base latency**, a production benchmark or a
research-target achievement. Production-sized Transformer latency remains
unmeasured. Runtime libraries: torch 2.14.1, transformers 4.57.6, safetensors 0.8.0.
Private smoke datasets, weights and report remain under ignored `data/l2/`;
`models/artifacts/` is also ignored. Git tracks no collected data.

### Verification and remaining work

The final offline suite and configured synthetic-model integration check are
recorded below. New tests cover lexical evidence/uncertainty/multilingual
normalization, input integrity, exact gating, compatibility before ranking,
bootstrap/model separation, upstream replacement, pending/force, batch/member
failures, cached offline loaders, probabilities/thresholds/manifests, deterministic
exports and executed SQL/Flask counts/filters/history/private detail. Existing
L0/L1 and collection tests remain passing. Compilation and diff whitespace checks
pass; missing model CLI exits 2 before cloud access, with an explicit configuration
message. No model binaries or private data were staged/committed.

At the end of the initial implementation pass, **no research-trained AfroXLMR GBV model,
real-corpus L2 annotation run, full
inference coverage, independent human L2 reference set, calibration or final
accuracy/precision/recall/F1/AUC was produced.** No production infrastructure,
production data, public roadmap or deployment was changed. Next work requires
reviewing the provisional study rules/codebook and upstream validation, agreeing
development/held-out membership, selecting/pinning the real base checkpoint,
performing an explicitly approved training/run scope, and independent sampled
validation before research exit-gate claims.

Final checks on 5 October 2026:

* `.venv/bin/python -m unittest discover -s tests -q`: **238 tests run;
  237 passed, 1 optional local-model integration test skipped** (3.495 s).
* `GBV_L2_INTEGRATION_MODEL=data/l2/synthetic-smoke-20261005/tiny-trained
  .venv/bin/python -m unittest tests.test_l2_model -q`: **10 tests passed**,
  including the real local tiny-artifact integration (2.996 s); no download.
* Python compilation and `git diff --check` passed. `git ls-files data` returned
  no tracked data; `git check-ignore` confirms synthetic manifests/weights and
  `models/artifacts/` outputs are excluded.

### Weak bootstrap result tiles — 5 October 2026

The existing read-only L2 weak results page now includes clickable `gbv`,
`not_gbv` and `borderline` tiles with live grouped counts from the compatible
weak-supervision cohort. Counts span pages and labels while respecting source/
method/model-version filters. Links retain the filter context, select a label and
reset pagination; zero-count categories remain visible. Historical and Transformer
rows do not inflate bootstrap totals. No annotation rules, model methods, database
schema, stored labels or public planning rows were changed.

`.venv/bin/python -m unittest tests.test_l2_ui tests.test_annotation_routes -q`
passed all **15 tests**, including new executed SQL/Flask checks for current vs
historical rows, weak/model separation, filtered counts, links, pagination reset
and empty-source categories. `git diff --check` passed. Restart the local Flask
process to load the updated route/service before refreshing the weak results page.

### L2 protected Human Review — 5 October 2026

The user's follow-up request extends the existing local review workflow to L2.
Roadmap sync succeeded; all four remote exports match the current snapshots.
This supports the L2 implementation/validation work; public planning rows and
research exit gates remain unchanged.

* L2 weak bootstrap and model rows now open the shared review workspace. Reviewers
  can unlock directly, inspect verified full text, exact L1 lineage, weak votes or
  model metadata, and confirm/correct gbv/not_gbv/borderline or leave an unresolved
  decision. The old exact-L2 URL redirects to this workspace.
* Separate dashboard counts/status filters distinguish weak reviews from model
  reviews. Navigation and Save & Next preserve label, source, review status, mode
  and method/model versions. Current compatibility and exact annotation UUIDs
  prevent old reviews from being inherited by new machine results.
* The additive `20261005_add_l2_human_validations.sql` extends three named checks;
  it preserves existing rows, indexes, RLS and foreign keys. Missing L2 constraints
  block saves/status filters with a migration notice instead of a false conflict.
  It was applied to the configured development Supabase database; constraint
  inspection passed and machine/human row counts were unchanged. The local Flask
  monitor was restarted on port 8080. No real human decision was fabricated.
* Existing local-token, CSRF, expiry, private-text verification, revision/stale-form
  protections and append-only storage remain in use. No research model training,
  annotation rerun or validation-completion claim is introduced.

Validation: **249 tests run, 248 passed, one optional installed-model integration
test skipped**. Nine new executed synthetic L2-review tests cover saved decisions,
immutable machine rows, revisions, stale forms, unresolved/cross-layer labels,
method separation, navigation, new-result review isolation, local/remote/CSRF
security and migration readiness. Python compilation and `git diff --check`
passed; `git ls-files data` returned no tracked research artifacts.
Read-only live HTTP checks passed for both L2 dashboard review sections, the weak
pending-review list, the direct L2 unlock form and private/no-store response headers.
Locked sessions expose no save control; live verification created no reviews.

### Documentation consistency audit — 5 October 2026

Updated all eight project-maintained Markdown guides against source behavior,
dated executed test evidence and current read-only development aggregates/schema:

* [Root README](../../README.md): coverage table, local run/stop/test commands,
  model-unconfigured meaning, pending-only weak execution, direct L2 unlock and
  explicit migration readiness.
* [AGENTS.md](../../AGENTS.md): accepted implemented architecture, current priorities,
  v2/weak/review progress and remaining research gates, without weakening research rules.
* [AI_CONTEXT.md](../AI_CONTEXT.md): source tree, ML state, L0/L1/L2 orchestration,
  review storage, current vs historical counts and future work.
* [Annotation specification](../annotations.md): actual CLI/layer support, schema,
  weak/model coverage separation, local review, current test evidence and limitations.
* [Deployment notes](../app_engine_deployment.md): per-target migration verification,
  development schema gap, remote-review restrictions and optional artifact configuration.
* [Collection protocol](../collection_protocol.md): downstream annotation/review handoff
  while preserving broad collection, archive sampling and privacy constraints.
* [Roadmap guide](README.md): successful latest sync, current planning/engineering
  mismatch and the separation between execution coverage and research gates.
* This engineering log: current verified coverage, schema readiness, latest snapshot
  hashes and explicit historical labeling of older test/run evidence.

The three vendored `annotations/resources/upstream/*/README.md` files were preserved
as pinned source evidence; the offline gazetteer `--check` passed. They are upstream
documentation, not repository progress guides. No private article text, identity,
reference labels or credentials were added. No public Sheet/CSV, application code,
annotation, model, cloud resource or database schema was changed by this audit.

Checks passed: local Markdown links/anchors and code fences across all eight guides,
actual annotation CLI help/options, offline gazetteer verification and
`git diff --check`. The latest full-suite result remains the previously executed
249 tests (248 passed, one optional model integration test skipped); tests and
research pipelines were not rerun for documentation-only edits.
