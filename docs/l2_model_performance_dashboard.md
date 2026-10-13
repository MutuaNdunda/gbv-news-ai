# Private L2 Model Performance dashboard

## Model Performance status — 13 October 2026

`L2-VALIDATION-V1` was completed on **13 October 2026 at 16:19:19 EAT**; its first private development-validation report was generated at **16:22:39 EAT**. The unchanged model is `l2-afroxlmr-dev-v1`, method `l2-47035d92f81cd5240062610d`, with original 0.80/0.20 thresholds. This is development validation, not final held-out testing or a newly trained model.

Open the completed batch to load its existing report; viewing does not require
a new evaluation. Full results, actual supports, confidence intervals, confusion
counts, abstentions and subgroups are recorded privately in `data/l2/evaluation-notes/L2-VALIDATION-V1-v1/MODEL_PERFORMANCE_RESULTS.md`.

The 400 accepted workflow decisions contain 342 binary references and 58 semantic borderline exclusions. Title-only evidence (381/400), frozen-instrument reconciliation, publisher scope, unverified language metadata and near-duplicate risks remain interpretation limits. A completed batch and a private report do not establish a gold standard or close the research gate.

For a new researcher capability, run `openssl rand -hex 32`, put the generated
64-character value in `.env` under `MODEL_PERFORMANCE_TOKEN`, enable
`MODEL_PERFORMANCE_ENABLED=1` and restart Flask. Do not use the review token or
publish the generated secret. No actual credential is included in this guide.

The previous pre-completion procedure below remains guidance for future batches;
it is not an instruction to re-review or re-complete the sealed current batch.

Implemented 13 October 2026. This extends the existing completed-batch evaluator;
it does not by itself establish accepted research performance. Initial implementation
left the live batch in review. The researcher subsequently completed it and
authorized its first private evaluation. Evaluation changed no label, prediction,
threshold or trained model.

## Historical pre-completion development preflight

The read-only audit at **13 October 2026, 16:08:37 EAT** found one batch named
`L2-VALIDATION-V1`, purpose `development_validation`, random seed 42, status
`in_review`, protected from training. Requested/actual membership is 400/400;
initial/final pointers are 400/400. Human support is **92 GBV, 250 Not GBV and
58 semantic borderline**. Thus 400 resolved workflow decisions supply **342 binary
human references**, before application abstentions are considered. There are zero
unable-to-determine/needs-adjudication decisions. No performance scores were run.

The exact artifact/method matches `l2-afroxlmr-dev-v1` /
`l2-47035d92f81cd5240062610d`. Frozen membership integrity, exact article/version/
prediction/guideline lineage, exact body deduplication and exclusion against all
322 actual training records plus historical training hashes passed. No reference
or training overlap issue was detected. This verifies exact exclusions, not
near-duplicate or incident-family independence.

Recorded evidence remains **381 title-only (95.25%), 10 verified-body access and 9 other/
unknown**. One distinct configured reviewer identity is recorded; independent
multi-person annotation and inter-annotator agreement are not established.
Body opening is not evidence of correct reading or labeling.

The frozen instrument is a checksum identifier for `docs/annotations.md`, rather
than the named finalized codebook identifier. Preserve it. Reconcile the archived
instrument, codebook semantics, title-only deviation and feedback-exposed revision
policy privately before research acceptance; changing the environment identifier
does not amend frozen history.

The pinned frame has 1,095 eligible candidates, with blank source/language filters.
Batch publisher support is Nation 98, Citizen 38, Star 155, Taifa Leo 106,
Kenyans.co.ke 2 and Tuko 1; Standard is absent. The latter two publishers require
scope reconciliation against the draft formal five-publisher protocol. Raw language
tags are `en` 256, `en-KE` 38 and unknown 106. Taifa Leo is not silently assigned
Swahili. Catalog publication dates are missing for 280 members; this audit did not
read private normalized body objects to independently assess date/language quality.
Near duplicates, archive/frame bias, approved publication window, linguistic
competence, independent adjudication and protocol acceptance remain limitations.

Detailed batch UUID, membership/artifact/guideline hashes and metadata audit are
stored privately under ignored `data/l2/reference-audits/`. The original morning
observation remains in [the coverage report](research/l2_human_validation_progress_20261013.md).

## Enable the local researcher workspace

Retain the existing valid Human Review configuration and frozen guideline identity.
Configure these additional environment settings privately, then restart Flask:

```text
MODEL_PERFORMANCE_ENABLED=1
MODEL_PERFORMANCE_TOKEN=<a separate strong researcher token, at least 32 characters>
MODEL_PERFORMANCE_REPORT_ROOT=data/l2/evaluations
```

The report root defaults to repository-anchored `data/l2/evaluations`; overrides
must resolve under ignored repository `data/`. Relative overrides are resolved
against the repository, not an arbitrary server working directory.
The researcher token must differ from `HUMAN_REVIEW_TOKEN`. Model Performance
uses its own session binding, 30-minute expiry and CSRF-protected unlock, and cannot
be unlocked by a Human Review session. Neither feature is remotely accessible:
direct localhost host/address and absence of proxy forwarding headers are required.
Default-disabled settings and `.env` were not changed by implementation.

| Route | Behavior |
| --- | --- |
| `/annotations/model-performance` | Batch selection, pending progress, persisted completed metrics, research diagnostics and private export links. |
| `/annotations/model-performance/<batch_id>/errors` | Paginated protected comparisons; filter TP/TN/FP/FN, abstentions, human uncertainty, publisher, raw language, score range and evidence basis. |
| `/annotations/model-performance/<batch_id>/errors/<member_id>/body` | Explicit private body read through the existing verified reader; missing pinned generation fails closed. |
| `/annotations/model-performance/<batch_id>/export/<name>` | Allowlisted checked exports, requiring researcher capability and completed evidence. |
| `/annotations/model-performance/<batch_id>/reference-audit` | Human Review capability; metadata-only blinded title-evidence list and reproducible proposed quality sample. No model results or disagreement selection. |

No independent reviewer-assignment registry exists. Consequently all model
comparisons, including metrics, bodies and exports, fail closed while **any** batch
is `frozen`/`in_review`, even if a researcher has a performance token. Pending
progress/reference audits remain available. This conservative global restriction
avoids inventing assignment-level authorization. The existing ordinary monitor can
still show predictions; it is not a general reviewer-isolation system. Reviewers
must use the protected blind routes before any ordinary model inspection.

Every performance response, including errors/unlock/downloads, has private/no-store,
no-referrer, no-index, frame-denial and MIME-sniff protection. Body JSON is rendered
with `textContent`, not HTML. No headline, body, review reason or reviewer identity
is included in default exports. Private diagnostics display catalog headlines and
dates; these may differ from the verified pinned body. No new migration, dependency,
public deployment or authenticated remote-review design is introduced.

## Reference-quality procedure and future-batch completion

1. Inspect the protected reference-quality audit and its title-only list. Agree
   evidence sufficiency, protocol/publisher scope, codebook reconciliation,
   uncertainty treatment, near-duplicate risks, reviewer competence and accepted
   initial-versus-post-feedback revision policy. No approval is inferred here.
2. If needed, approve a blinded quality-audit sample. The proposed default uses seed
   **20261013**, up to **two** references per accepted binary human label × publisher
   × recorded evidence stratum; it selects without model scores, errors or
   disagreement. It is a proposal, not a created assignment or a representative
   estimate. Small strata can be censuses. Agree language/second-review coverage
   and sample size first; do not automatically re-review all 400 members.
3. Audit links use the existing single-review revision path with `blind=1`.
   Model comparison remains absent after saving and through Save & Next.
   Generation/hash-verified body retrieval records verified access on subsequent
   single-review notes. Initial decisions and history remain unchanged; revisions
   append and advance the existing final pointer with stale-form protection. The
   history still shows previous human decisions; independent A/B annotation is
   not supplied. Do not reopen or alter a completed sealed batch.
4. After the researcher explicitly accepts references and limitations, unlock
   **L2 Validation → L2-VALIDATION-V1 → batch progress**, acknowledge the research
   quality statement and press **Complete · freeze accepted decisions**. The
   existing protected completion transaction and database guards remain the only
   lifecycle mechanism. The route rechecks integrity/training exclusion first;
   unresolved/semantic borderline decisions remain retained exclusions. This task
   has not performed this action and does not declare the thesis gate achieved.
5. After separately authorizing the first private evaluation, run:

   ```bash
   .venv/bin/python scripts/evaluate_l2_validation.py \
     --batch L2-VALIDATION-V1 \
     --output-dir data/l2/evaluations/L2-VALIDATION-V1-v1
   ```

   If that directory already exists, choose a new version. Outputs never overwrite
   prior evidence. Do not use `--final-experiment` for development validation.
6. Open Model Performance with the separate researcher token. Completed batches
   without an explicitly generated report show a missing-report notice. In-review
   batches always show **“Evaluation pending — human reference batch has not been
   completed.”** GET does not run the evaluator, inference or any mutation.

Repeatable read-only preflight (new private output directory each time):

```bash
.venv/bin/python scripts/audit_l2_references.py \
  --batch L2-VALIDATION-V1 \
  --output-dir data/l2/reference-audits/L2-VALIDATION-V1-next-audit
```

This uses a consistent read-only PostgreSQL snapshot, batched parameterized queries,
checksummed local artifact/training metadata and historical-hash exclusion. It does
not load Transformer weights for execution, read article bodies, calculate scores
or write to the database. Private `audit.json` includes audit candidate headlines;
stdout contains aggregate metadata. Technical integrity, completed evaluation
readiness and research-quality acceptance are distinct fields.

## Shared calculation definitions

Metric definition **`l2-human-evaluation-v2`** lives in
`annotations/l2_evaluation.py`. The existing `evaluate_rows` wrapper validates
completed status, ordered membership SHA-256, exact model identity, valid pinned
score/threshold decisions, and the accepted human pointer/guideline. It never uses
weak labels, training labels, machine labels or the ordinary latest-review overlay
as a human reference. The operator CLI additionally verifies initial/final chains,
extraction hash, member status and exact training exclusion. All probabilities must
be finite in [0,1]; invalid pinned evidence fails the report closed.

Both Flask and the CLI consume the same report structure. Flask loads previously
persisted reports; it does not duplicate scientific calculations in routes or
JavaScript. The legacy four-key `metrics` field remains available, with richer
definitions in `classification.metric_details`. Undefined results are null with
a reason, and shown as N/A. A missing human class has undefined class metrics;
macro averages require both classes. Weighted averages include supported classes
and remain undefined if a required supported class metric is undefined.

Let TP/FP/TN/FN use only human `gbv`/`not_gbv` references whose original model
decision is also binary. Matrix rows are **model** and columns are **human**:

| | Human GBV | Human Not GBV |
| --- | --- | --- |
| Model GBV | TP | FP |
| Model Not GBV | FN | TN |

Let B = TP+FP+TN+FN, R = all binary human references and N = frozen members.

| Quantity | Numerator / denominator |
| --- | --- |
| Conditional accuracy | (TP+TN) / B; never whole-sample accuracy |
| GBV precision / recall / F1 | TP/(TP+FP); TP/(TP+FN); 2TP/(2TP+FP+FN) |
| Not-GBV precision / recall / F1 | TN/(TN+FN); TN/(TN+FP); 2TN/(2TN+FN+FP) |
| Macro precision/recall/F1 | Unweighted mean of the two defined class values |
| Weighted precision/recall/F1 | Class-support weighted sum / B |
| Micro precision/recall/F1 | (TP+TN)/B for this single-label binary subset |
| Balanced accuracy | Mean of class recalls |
| Specificity / FPR / FNR / NPV | TN/(TN+FP); FP/(TN+FP); FN/(TP+FN); TN/(TN+FN) |
| Binary coverage | B/R |
| All-member model abstention | Original model borderline count / N |
| Binary-reference model abstention | Borderline model decisions among R / R |
| Human uncertainty exclusions | N−R, including semantic borderline and unresolved/adjudication decisions |

The page shows counts, denominator/support and definitions with each metric.
Model borderline is an application abstention, not a learned third class. It is
neither correct nor incorrect in binary metrics. Human GBV/Not-GBV abstention counts
are separate. Exact original positive/negative thresholds are pinned in evidence;
dev-v1 remains **0.80/0.20**. No score is replaced by a threshold experiment.

## Probability and threshold analysis

Probability metrics use **all R references**, including model abstentions, with
their exact original stored GBV softmax scores. ROC-AUC groups tied scores and
integrates trapezoids. Average precision (the report's `pr_auc` compatibility key)
is **Σ Δrecall × precision** at distinct descending scores, not trapezoidal PR-AUC.
Both AUCs are withheld unless both human classes occur; small support is warned.
The page plots ROC and PR curves and reports sample prevalence.

Brier score is mean (p−y)². Log loss is mean −[y ln p+(1−y) ln(1−p)], clipping
scores to [1e−15, 1−1e−15] solely for numerical logarithms. Descriptive reliability
uses ten equal-width bins [lower, upper), with the last bin including 1; empty bins
are N/A. ECE = Σ (bin count/R) × |mean score−observed positive fraction|. Class
score distributions and per-bin support are retained. No calibration model is
fitted, and softmax scores are not described as calibrated true probabilities.

Development-only threshold rows explore symmetric intervals for positives
0.50, 0.60, 0.70, 0.80, 0.85, 0.90 and 0.95, with negatives 1−positive. The 0.50
tie is assigned positive. The table includes precision, conditional recall,
coverage/abstention, FP/FN and selective risk = errors/non-abstaining support.
GBV detection rate = TP/all binary human GBV, including abstentions, distinguishes
conditional recall from operational coverage. All denominators are retained.
These are **exploratory development analyses, not final-test results or validated
improvements**. Original predictions remain unchanged. Final-test and diagnostic
batches have no threshold exploration. Final-test report loading also requires
the explicit `--final-experiment` CLI release marker; no new test batch is created.

## Subgroups and uncertainty

Publisher tables contain only observed publishers, without fabricated Standard
support. Language groups normalize explicit English/Swahili/Sheng/mixed metadata;
unrecognized or absent tags remain Unknown. Publisher never assigns language.
All groups include N, human/model support, abstentions, binary support and metrics.
N<30 or fewer than ten evaluable references in either class triggers a small-support
warning. These cutoffs are reporting cautions, not approved adequacy thresholds or
fairness tests. There are no rankings, language competence assumptions or proven
fairness-disparity claims.

Rate intervals use Wilson score 95% with z=1.959963984540054 and their own binary
denominators. F1/macro-F1 use a deterministic article-level percentile bootstrap,
**1,000 resamples, seed 20261013**, withheld unless each evaluable human class has
at least ten references. A bootstrap metric is withheld if fewer than 95% of
replicates are defined. This uses an IID article assumption; incident/syndication
clusters are unavailable. Narrow intervals do not resolve sampling, reference-label
or duplicate-family bias. No model-human agreement is called Cohen's kappa or
Krippendorff's alpha.

## Persistence, exports and implementation inventory

Immutable private bundles contain `evaluation_pairs.jsonl`, `evaluation_report.json`,
classification/confusion/subgroup/error CSVs and `manifest.json`. The SHA-256 manifest
checks every deterministic evidence/table file. Loading rechecks batch/model/
purpose/guideline/configuration, membership integrity, extraction lineage and exact
initial/final reference pointers. Symlink/traversal paths, corrupted files and
legacy reports fail closed. Generate a new v2 report directory instead of modifying
old artifacts. The newest bundle for a selected batch is loaded; a corrupt latest
bundle produces an error rather than silently switching evidence.

Code commit, implementation-file SHA-256s, model/training manifests, membership,
seed and metric version remain pinned. Deterministic report content uses the
immutable reference-completion timestamp as an explicitly described time anchor;
actual UTC calculation time is in `invocation.json`, with its own checksummed
`invocation_manifest.json` bound to the exact report hash. Thus identical evidence
produces identical mathematical artifacts without inventing an identical wall time.
Default exports include these manifests/time metadata, summary JSON and CSV tables;
raw JSONL pairs are CLI-private only. Spreadsheet formula prefixes are escaped.
Directories/files use 0700/0600 permissions; all remain ignored by Git.

Changed/new responsibilities:

- `annotations/validation_batches.py`: existing accepted-reference resolution and
  backward-compatible report entry point, threshold/model/reference guards.
- `annotations/l2_evaluation.py`: classification, abstention, probability, subgroup,
  threshold and interval definitions.
- `annotations/reference_quality.py`: evidence/lineage/independence audit and blind
  sample proposal, without model-disagreement selection.
- `annotations/evaluation_reports.py`: private immutable bundles, CSVs/checksums,
  invocation metadata and protected loading.
- `database/repositories/validation_batches.py`: consistent batched snapshots,
  initial/final chain audit, global active-blind guard, verified single-review notes.
- `scripts/evaluate_l2_validation.py` and `scripts/audit_l2_references.py`: shared
  evaluation and read-only preflight operators.
- `app/services/model_performance_service.py`, `app/routes/model_performance.py`,
  templates/static CSS/JS and app/navigation registration: protected presentation,
  diagnostic body reads and export access.
- Existing validation routes/templates: explicit completion acknowledgment and
  permanently blind quality-review links using append-only revisions.
- `tests/test_model_performance.py` and the existing evaluator CLI regression:
  synthetic metrics, lifecycle, access, lineage, no-write/no-inference GETs,
  abstentions, checksums, deterministic resampling and quality warnings.

The first live private development artifact now exists at `data/l2/evaluations/L2-VALIDATION-V1-v1/evaluation_report.json`.
`L2-VALIDATION-V1` is completed and its accepted pointers are sealed. Do not
re-complete or reopen it; load the existing report to inspect performance.
Synthetic completed/pending/error HTML previews were generated under `/tmp` for
inspection. Browser integration was unavailable in this session; no screenshot
or visual layout certification is asserted. Template render tests passed.

## Executed verification

Final full offline suite: **432 tests run, 431 passed, one skipped**, zero failures.
The skip is the existing optional installed-model integration test because
`GBV_L2_INTEGRATION_MODEL` was not explicitly configured; no real model inference
was enabled for this reporting task. Twenty-two new performance tests cover metric
formulas/edge cases, abstention cohorts, tied-score AUC/AP, calibration, threshold
purity/final-test restriction, subgroups, deterministic intervals, completed-only
reports, access separation/expiry/proxies, active-blind blocking, verified bodies,
append-only blind revisions, lineage/checksums, title evidence and completion leakage
rejection. The existing private CLI deterministic/no-overwrite regression remains
passing with explicit synthetic training provenance.

`git diff --check`, Python compilation, JavaScript syntax and private-audit Git
exclusion checks passed. `git ls-files data` returned no tracked data files. The
private report root contained zero evaluation reports at the implementation check.
The pre-completion read-only live audit confirmed `in_review` status, membership digest, labels/evidence,
400 initial/final pointers, zero chain/threshold/probability/lineage issues, zero
exact duplicates and zero exact training overlap. No dataset, `.env`, model
checkpoint or private audit was staged, committed or pushed.
