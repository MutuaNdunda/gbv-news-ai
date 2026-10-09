# Create the first independent L2 validation dataset

Updated **8 October 2026 (EAT)**. This is the operator guide for preparing
`L2-VALIDATION-V1`, a **development-validation reference batch** for the existing
`l2-afroxlmr-dev-v1`. It does not create a batch, approve the draft sampling protocol,
change the finalized semantic codebook or authorize retraining/final testing.

Read the [finalized codebook](l2_gbv_relevance_codebook_v1.0.md),
[draft sampling protocol](l2_validation_sampling_protocol_v1.0.md),
[annotation implementation](../annotations.md#22-l2-validation-and-protected-reference-workflow)
and [current engineering status](../roadmap/IMPLEMENTATION_STATUS.md) together.
The implementation supports dataset creation; research readiness depends on the
agreed design and actual unseen eligible support.

## 1. Establish the frame and decisions before creating a draft

Record privately the intended publication window, formal publishers, sampling
strategy/size/seed, minimum positive and subgroup support, reviewer competence and
prior exposure, handling of unresolved/abstaining cases, duplicate-family policy,
accepted-reference/revision policy, second-review/adjudication requirements and
performance acceptance criteria. The sampling protocol lists the outstanding
research/supervisor decisions; this guide does not mark them approved.

Set formal source keys explicitly:

```text
nation,standard,star,citizen,taifaleo
```

The `citizen` key represents Citizen Digital digital articles; reconcile its
Citizen TV proposal mapping in the approval record. Tuko and Kenyans.co.ke belong
to separately identified engineering/diagnostic work unless formal scope is amended.
A blank UI source filter includes all seven supported publishers.

Use an agreed `random` design or proportional source × **raw language metadata**
`stratified` design. The current UI does not implement publication-period filtering,
reviewed-language quotas, near-duplicate/syndication grouping or independent
Reviewer A/B adjudication. Resolve required unsupported controls before freezing;
a checkbox or a larger N does not supply them. Do not use `enriched` for an
independent assessment: it is diagnostic only and suppresses representative metrics.

## 2. Verify coverage and independence

Each candidate needs current compatible **L0 valid → L1 kenya → exact dev-v1 model
prediction**, readable generation/hash-verified private content, and the agreed
study membership. Collection counts alone do not establish this eligibility.
Inspect `/annotations` for pending L0/L1/L2 and `/annotations/runs` for execution
status. Agree and separately authorize any remaining annotation scope before
running it; this documentation task does not run annotations.

The first model trained on **all 322** mixed-effective binary records, not just
human-reviewed positives. Independent selection excludes training article IDs,
extraction-version IDs, body hashes and historical hashes for those articles.
A new extraction of the same training article is not independent. Frozen protected
batches and exact duplicate bodies are excluded too. Near-duplicate and syndication
handling remains an agreed research control beyond native exact-hash exclusion.

The historical 324-result cohort offered at most two records before additional
filters. Expansion can improve support only after the new candidates pass gates
and receive compatible pinned predictions. Consult the latest dated readiness
observation in the implementation log; perform the real UI preview again before
creation. Metadata-only screening is an upper bound, not a verified GCS/language/
publication-window/duplicate-family sampling frame.

## 3. Verify the intended database and local reviewer configuration

From the repository root, with the existing project environment:

```bash
.venv/bin/python scripts/check_l2_validation_schema.py
```

Exit 0 / `ready: true` with `missing: []` is required. Exit 1 means missing schema;
exit 2 means configuration/connection failure. The development validation migration
was installed and behavior-tested on 6 October; recheck readiness rather than
blindly reinstalling it. Other targets require their own checks and intended-target
installation from the [README](../../README.md#l2-validation-and-protected-reference).
Readiness is not a full RLS/permission-definition audit or research approval.

Configure privately and restart the local app:

```text
HUMAN_REVIEW_ENABLED=1
HUMAN_REVIEW_TOKEN=<private strong token, at least 32 characters>
FLASK_SECRET_KEY=<private strong signing key, at least 32 characters>
HUMAN_REVIEWER_ID=<agreed reviewer identity>
HUMAN_REVIEW_GUIDELINE_VERSION=l2-gbv-relevance-codebook-v1.0
L2_MODEL_PATH=<existing immutable dev-v1 artifact directory>
L2_MODEL_VERSION=l2-afroxlmr-dev-v1
```

Use direct `localhost`/`127.0.0.1`. Remote/proxied Human Review is blocked, including
HTTPS. Do not change the configured model, preprocessing or thresholds to obtain a
more convenient sample. Training provenance and artifact checksums must verify.

The separate `20261008_add_collection_run_control.sql` migration enables heartbeat/
Stop for **updated collection workers**; it is not the validation-batch migration
and does not unlock reference creation. It was not installed in the Runs task.
If further collection is needed, install it on the intended target before updated
trial/monthly execution. See [collection control](../collection_run_control.md).

## 4. Preview, create and freeze in the existing UI

1. Open `/annotations/validation`, unlock with the private review token, and select
   **Create Validation Batch**. Do not begin through ordinary model-result review.
2. Enter the versioned name `L2-VALIDATION-V1`, purpose `development_validation`,
   the configured dev-v1 identity, agreed N, strategy and seed. Select **Protect
   from training** and the formal five source keys. Language filters use exact
   unvalidated stored values; do not substitute them for verified language review.
3. **Preview** first. It is read-only: it checks schema, training provenance,
   current gates/model lineage, protected/exact-hash exclusions and GCS content.
   Record the eligible-pool size, exclusion counts, chosen configuration and
   membership digest privately. The preview does not save a batch or protect it.
4. If unseen support is below N, stop and resolve the eligible frame. Do not lower
   N merely to bypass a scientifically inadequate sample, recycle training members,
   or relabel a diagnostic batch as independent validation.
5. Create the **draft** only once the design/frame requirements are satisfied.
   A draft stores selected membership but does not yet exclude it from training.
   Archive the agreed protocol/codebook checksums, model/training identity, source/
   period/language decisions, eligible-frame evidence and deviations privately.
   Native storage records selected membership/configuration, not the full eligible
   frame archive; any required supplementary archive must be prepared explicitly.
6. **Freeze**. The app rechecks exact lineage, provenance, exclusions, requested
   count and selected digest; it does not resample. Frozen protected membership is
   excluded from subsequent protected exports/training. Avoid concurrent training
   and freezing; low-level training functions are outside this database safeguard.

Lifecycle: **draft → frozen → in_review → completed**. Do not overwrite/resample a
frozen batch to obtain favorable labels. Use a new versioned design when appropriate,
with disclosed reuse and the existing protection boundaries preserved.

### Session recovery after a slow preview

Reload the creation page after an app update so it issues the current validation
form token. Validation management and article-review forms now have separate CSRF
tokens. A successful authorized preview renews the 30-minute review window after
cloud verification; draft creation still rechecks the preview and digest.
If access expires before submission, the app asks you to unlock again, saves no
batch and restores your batch settings for a fresh preview. It does not replay
Create/Freeze/Complete automatically. Missing or stale CSRF still blocks submission
and explains that the page must be reloaded. Keep local access and training protection
enabled; do not disable security to recover. Database failure on results pages
offers a retry response rather than exposing SQL details.

## 5. Review without contaminating the initial references

Use **Review Next** in the frozen batch. Before the first decision the form hides
machine labels/probabilities/evidence. Independently assign `gbv`, `not_gbv`,
semantic `borderline`, `unable_to_determine`, or `needs_adjudication` under the
codebook. Human decisions remain separate and append-only.

Development comparison is revealed after saving. Ordinary result pages and human
aggregates remain accessible: avoid them before independent review and record
prior exposure. This is initial-form blinding, not isolated reviewer accounts.
Do not revise a reference merely to agree with the revealed model. The evaluator
scores the **accepted final pointer**; the protocol must approve how initial
blind decisions and later revisions/adjudication become accepted references.
Native independent double annotation and dedicated adjudication are absent.

Review all members, resolve referrals under the agreed policy, and confirm support/
uncertainty requirements before **Complete** locks final accepted pointers.
Software completion permits unresolved and semantic-borderline cases; it does not
certify research acceptance or adequate positive/language/publisher support.

## 6. Export evaluation pairs and report the limits

After an approved completed development batch, write to a new private directory:

```bash
.venv/bin/python scripts/evaluate_l2_validation.py \
  --batch L2-VALIDATION-V1 \
  --output-dir data/l2/evaluations/L2-VALIDATION-V1-v1
```

This produces immutable private `evaluation_pairs.jsonl`, `evaluation_report.json`
and checksum evidence, without retraining or inference. It validates pinned
membership/model/article/codebook/review lineage. It refuses directory overwrite.
Development/training dataset exporters are **not** the reference-batch creation
mechanism; a weak/mixed training export cannot establish independent validation.

Report TP/FP/TN/FN, total/reviewed/resolved/binary support, excluded uncertainty,
model abstentions and positive precision/recall/F1 alongside conditional accuracy.
Native scores exclude model-borderline and non-binary human pairs; positive
references on which the model abstains are not included in native FN. These are
conditional metrics, not whole-pipeline recall or corpus prevalence. Native macro-F1,
AUC, calibration, intervals, subgroup metrics and adjudication agreement are not
computed; required additional analyses need an agreed audited procedure.

This first development validation is not the untouched final thesis test. Preserve
its protected membership; agree later model/threshold reuse and a separate frozen
final-test design before any retraining or final-performance claims.

## 7. Git and privacy checkpoint

Keep full article content, reference membership, decisions, frame archives and
private reports under ignored `data/` or private GCS/Supabase. Commit code and
public methodological/operational documentation only. Before a commit/push:

```bash
git status --short
git ls-files data
git diff --check
git diff --cached --stat
```

Tracked `data/` output must contain only intentional README/placeholder files.
Never force-add ignored research data or secrets. See the
[Git push diagnostic](../git_push_diagnostic.md) for the 8 October repository check.
