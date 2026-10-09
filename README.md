# GBV News AI

GBV News AI is a postgraduate research project that aims to develop an ethical, human-supervised system for identifying, classifying, geotagging, and mapping gender-based violence (GBV) reporting in Kenyan digital news. The planned system will investigate multilingual approaches for English, Swahili, Sheng, and code-switched content, where available.

The collection pipeline and automated L0 extraction-quality / L1 Kenya-relevance
layers are operational. L2 weak supervision, training/inference infrastructure and
protected local L0/L1/L2 Human Review are implemented. No validated final research
dataset is available yet. The 8 October read-only audit observes 2,119 article
versions; the public roadmap retains a historical 536-version planning observation
and 407 was an older snapshot. Automated results still require sampled
human validation. Reporting sources include Daily Nation, Citizen Digital, The
Standard, The Star Kenya, Tuko, Kenyans.co.ke, and Taifa Leo, with collection
intended to include both GBV-related and non-GBV reporting. Current trials use
archived publisher reporting, as described below.

The repository includes a Flask monitor for collection and automated annotations,
with an optional protected, bounded annotation trigger and a protected local Human
Review workspace. Sampled human validation remains incomplete. The first
task-specific AfroXLMR development model is trained locally. Future work
includes larger-corpus retraining, independent multilingual evaluation, location
extraction, geocoding and mapping interfaces. Data collection and validation
come first. Privacy, provenance, reproducibility, and human oversight will guide
development throughout.

## Current progress — read-only audit beginning 8 October 2026, 22:50 EAT

The development corpus contains **2,119 articles / versions**. Compatible L0 covers
all versions (2,076 valid / 39 needs_review / 4 invalid); L1 covers all 2,076 eligible
versions (1,417 kenya / 130 not_kenya / 529 ambiguous). The unchanged dev-v1 model
has **1,417/1,417** compatible predictions (246 gbv / 1,049 not_gbv / 122 borderline),
zero pending within that eligible cohort. Validation schema is ready; zero real
validation batches/members exist. These outputs are not independently validated labels.

Training/exact-hash metadata screening found **1,089 potential unseen candidates**
in the formal five-source filter: Nation 285, Citizen 113, Star 392, Taifa Leo 299,
**Standard 0**. This is an upper bound before verified GCS content/language, study
period and near-duplicate/exposure checks. Resolve Standard support under the agreed
sampling design; do not claim five-publisher coverage from four represented sources.
Follow [Create the first independent L2 validation dataset](docs/research/validation_dataset_creation.md)
for design decisions, local setup, preview/create/freeze, review and private export.

The latest offline suite is **382 run / 381 passed / 1 optional integration skipped**,
zero failures. `/runs` supports SQL status filters and opt-in cooperative Stop;
its separate collection-control migration is not installed in the observed target.
It is required before updated collectors, not before reference-batch creation.
See [collection run control](docs/collection_run_control.md).

### Historical development baseline — verified 6 October 2026, 00:04 EAT

**Documentation update — 7 October 2026:** the researcher confirmed that
[L2 Codebook v1.0](docs/research/l2_gbv_relevance_codebook_v1.0.md) is finalized.
Shared bounded Wayback keyword discovery is implemented for all seven registered
publishers, with GCS/Supabase persistence and explicit live collection. The actual
seven-source smoke saved ten articles (five Citizen, five Kenyans.co.ke); four
sources hit CDX timeouts and Taifa Leo returned unsupported routes. The Citizen
body-layout fix subsequently extracted all five operator-reported warning pages;
that diagnostic check did not insert new article records. The later 7–8 October audits verified expanded corpus counts, summarized above;
this smoke record remains dated evidence and does not certify complete archive coverage.
The 536-version and annotation counts below are dated pre-expansion observations.
Sampling design, independent review/evaluation and the research exit gate remain
open; codebook finalization does not establish model accuracy.

Human-review state, reconfirmed at **22:59 EAT**: 324 eligible versions; original weak labels
7 gbv / 15 not_gbv / 302 borderline; human overlay **10 / 312 / 2**.
All 302 originally borderline results have reviews (300 corrections, two confirmed
borderline); 22 original binary weak results remain unreviewed.

The first real **`l2-afroxlmr-dev-v1`** development artifact is trained and configured
locally on 322 mixed-effective records (10 gbv, 312 not_gbv; only three positives
human-reviewed). Reviewed/mixed exports, weighted training and offline reload are
implemented. Twenty-record in-memory inference passed: 0 gbv / 19 not_gbv /
1 borderline, zero failures. **No reliable independent validation metrics exist.**
No final held-out human reference set is frozen; L2 research gates remain open.

The historical 6 October L2 operational closure verified **324/324 compatible Transformer predictions**:
**11 gbv / 307 not_gbv / 6 borderline**, with **zero pending**. The additive L2
migration is installed and behavior-tested in development. Pending-only resume
added 24 predictions without changing existing model, weak, human or L1 history.
The earlier interrupted run coincided with macOS idle sleep; model CLI runs now
prevent idle sleep and verify actual advisory-lock ownership before writes.
See [the L2 performance report](docs/l2_model_performance.md) for the diagnosis,
timing and remaining limitations. Original weak outputs remain separately
inspectable at `/annotations/l2?mode=weak`. Full offline suite including the
installed-model integration at operational closure: **275 tests passed**, zero skips.
The later validation-workflow suite passed **304 tests**, zero failures/skips. See
[the engineering log](docs/roadmap/IMPLEMENTATION_STATUS.md) for execution evidence.
L0 remains 519 valid / 17 needs_review; L1 v2 324 kenya / 35 not_kenya /
160 ambiguous. Independent research validation and L3–L5 remain pending.
Reproducible L2 batches, blinded initial review, protected reference exclusion and
private evaluation are now implemented in the existing local workspace. The new
validation migration is **installed and behavior-verified in development**; no real batch or independent
metrics were generated. The codebook is now researcher-finalized; agree the
sampling protocol and acceptance criteria before review;
see [validation setup](#l2-validation-and-protected-reference) and
[the validation specification](docs/annotations.md#22-l2-validation-and-protected-reference-workflow).

Development installation does not establish schema readiness for other targets.
Apply migrations in filename order and verify each target independently before
L2 writes. Production configuration was not changed.

## Sync project roadmap

The public Google Sheet is the planning source of truth. Sync its four tabs into
`docs/roadmap/` before roadmap-driven implementation:

```bash
python3 scripts/sync_roadmap.py
python3 scripts/sync_roadmap.py --check
```

No Google credentials are needed for roadmap synchronization. L0/L1 and L2
infrastructure are implemented; sampled-validation and research exit gates remain open.
The successful anonymous sync on 7 October records completed model training,
324/324 development inference and independent validation as the current priority.
All four snapshots were refreshed; the public Sheet was not changed.
Independent evaluation remains pending; synchronized CSVs are not manually edited.
See [the roadmap workflow](docs/roadmap/README.md) and
[implementation status](docs/roadmap/IMPLEMENTATION_STATUS.md).

## L2 validation and protected reference

Before a real batch, review the [L2 GBV Relevance Codebook v1.0](docs/research/l2_gbv_relevance_codebook_v1.0.md)
and [L2 Validation Sampling Protocol v1.0](docs/research/l2_validation_sampling_protocol_v1.0.md).
The codebook is researcher-finalized as of 7 October; the sampling protocol remains
a draft. They distinguish the five formal publishers from engineering sources.
Resolve sampling/support, review acceptance and documented implementation gaps
before `L2-VALIDATION-V1`. No separate supervisor/ethics approval or completed
research-validation gate is asserted.

Use the existing local Flask app and Human Review token/configuration. The new
**L2 Validation** navigation opens `/annotations/validation`; remote access remains
blocked. This workflow supports the configured `l2-afroxlmr-dev-v1` artifact.

The additive [validation migration](migrations/20261006_add_l2_validation_batches.sql)
was **installed in the configured development database on 6 October 2026 at
23:48 EAT**, after user authorization. The standalone checker returns `ready: true`
and `missing: []`; 15 rollback-only synthetic database checks passed. Existing
article, prediction and review fingerprints were unchanged. No real batch was created.
The 8 October read-only preflight again found this target ready, with no batches.
Run step 2 before every new operational session; skip installation only when that
intended target is ready. Follow the [dataset-creation guide](docs/research/validation_dataset_creation.md)
for current frame/support and protocol checks. Other targets require steps 1–3 independently:

1. Confirm the intended development database and existing annotation/human-review
   migrations. Do not infer installation from migration files.
2. Run the read-only preflight using the existing `.env` configuration:

   ```bash
   .venv/bin/python scripts/check_l2_validation_schema.py
   ```

   Exit 0 means ready, 1 means missing objects, 2 means configuration/connection
   failure. For a new installation expect both new tables and guards absent.
   If objects already exist partially, inspect their definitions before applying;
   the SQL deliberately refuses conflicting names rather than replacing them.
3. Apply **only** `migrations/20261006_add_l2_validation_batches.sql` once to that
   confirmed target using its SQL editor or an explicitly configured direct
   PostgreSQL connection. The SQL includes its own transaction. If `psql` and
   `DIRECT_DATABASE_URL` are configured for the intended target:

   ```bash
   psql "$DIRECT_DATABASE_URL" -v ON_ERROR_STOP=1 \
     -f migrations/20261006_add_l2_validation_batches.sql
   .venv/bin/python scripts/check_l2_validation_schema.py
   ```

   Require exit 0 afterward. Verify frozen membership and accepted-reference
   immutability on rollback-only synthetic records for each new target. Development
   passed these checks; installation on other targets is not established.
4. Restart the local app with the existing Human Review configuration. Unlock
   **L2 Validation → Create Validation Batch**. Choose `L2-VALIDATION-V1`, purpose
   `development_validation`, configured model identity, agreed sample size,
   `random` or proportional `stratified`, seed 42 (or record another seed), and
   **Protect from training**. Optional source/language filters narrow the pool.
5. Preview the available pool and membership digest, create a draft, then freeze
   membership. All **322** actual first-model training records and their historical
   body hashes are excluded. If only N unseen eligible records remain, the app
   refuses a larger sample. Collect/validate additional unseen articles under a
   separate agreed collection plan; do not relabel training data as independent.
6. Select **Review Next**, record the independent human label and reason, then
   inspect the pinned model comparison after saving. Review all members and
   complete the batch to freeze accepted final pointers. Unresolved/adjudication
   and human/model borderline remain explicit exclusions from binary evaluation.
7. Evaluate a completed representative batch into a new private directory:

   ```bash
   .venv/bin/python scripts/evaluate_l2_validation.py \
     --batch L2-VALIDATION-V1 \
     --output-dir data/l2/evaluations/L2-VALIDATION-V1-v1
   ```

Outputs are private JSONL pairs, a JSON report and deterministic hashes under
ignored `data/`. The report includes confusion counts, binary support, precision,
recall, F1, conditional accuracy and abstentions. `diagnostic`/`enriched` batches
may inspect training records but suppress representative metrics. No independent
model performance is established until an appropriate unseen batch is reviewed.

Frozen protected membership is automatically excluded from reviewed-only,
mixed-effective and weak-bootstrap exports and private priority selection. Manual
reference manifests remain supported. Training CLI rechecks older exports and
rejects newly protected membership before loading the model. These paths now fail
closed when the validation schema is missing. Avoid freezing conflicting batches
during an active training job; direct low-level training calls do not consult DB.

Final-test batches require protection and keep machine feedback hidden even after
review. Evaluation requires explicit `--final-experiment` for the approved final
experiment. Never use them for training, tuning, active learning or model selection.
No final-test batch is created automatically. This local workflow does not isolate
reviewers from ordinary machine-result pages; use the blind batch route before
inspecting predictions. Independent A/B reviewers and separate adjudication records
remain future work. See [the annotation specification](docs/annotations.md#22-l2-validation-and-protected-reference-workflow).

## Corpus Collection Monitor

The implemented Flask monitor provides an operational view of collection state, with opt-in protected cooperative Stop.
It provides corpus totals, grouped source/month counts, run and source/month scan
progress, searchable article metadata, complete extraction lineage, and infrastructure
health. Counts come from Supabase; GCS is consulted only for read-only bucket health.
Collection pages show metadata. Verified full text is available only in the
unlocked local Human Review workspace.

### Run the monitor locally

Run the following commands from the repository root. Create and activate a virtual
environment if one does not already exist:

```bash
cd /Users/mutua/Documents/Projects/gbv-news-ai
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Configure the required Supabase and GCS variables using the project configuration
described in `.env.example`. Do not commit credentials. Authenticate to Google Cloud
locally with Application Default Credentials; no service-account key file is needed:

```bash
gcloud auth application-default login
python3 scripts/test_infrastructure_connections.py
```

Apply the versioned scan-state migration once per database if it has not already been
applied:

```bash
psql "$DIRECT_DATABASE_URL" -f migrations/20260909_add_collection_run_scans.sql
psql "$DIRECT_DATABASE_URL" -f migrations/20260910_expand_collection_sources.sql
psql "$DIRECT_DATABASE_URL" -f migrations/20261003_add_taifaleo_source.sql
```

Start the application with Gunicorn:

```bash
gunicorn -b 127.0.0.1:8080 main:app
```

Open `http://127.0.0.1:8080/`. Available pages are:

- Dashboard: `http://127.0.0.1:8080/`
- Collection runs: `http://127.0.0.1:8080/runs`
- Articles and extraction lineage: `http://127.0.0.1:8080/articles`
- Infrastructure health: `http://127.0.0.1:8080/health`
- Automated annotation counts and runs: `http://127.0.0.1:8080/annotations`

For local development with debug mode and automatic reload, use:

```bash
flask --app main:app run --debug --port 8080
```

Stop either server with Ctrl-C. Collection Stop and annotation execution are
disabled by default; see the collection run control instructions below. If startup or `/health` fails, rerun
`python3 scripts/test_infrastructure_connections.py` and verify the configured database,
bucket, and ADC access before changing application code.

To stop a detached local server on port 8080 on macOS:

```bash
lsof -tiTCP:8080 -sTCP:LISTEN | xargs kill
```

Start the local review workspace without debug mode:

```bash
.venv/bin/python -m flask --app main:app run --port 8080
```

Run the offline regression suite with:

```bash
.venv/bin/python -m unittest discover -s tests -q
```

## Automated L0 and L1

Apply the additive annotation migration once per database, after the ingestion
migrations above. It has already been applied to the development Supabase database:

```bash
psql "$DIRECT_DATABASE_URL" -f migrations/20261003_add_automated_annotations.sql
```

Use the existing Supabase/GCS configuration and ADC credentials. Run a bounded
batch first, then use the appropriate scope:

```bash
python3 scripts/run_annotations.py --layer l0,l1 --limit 20
python3 scripts/run_annotations.py --layer l0
python3 scripts/run_annotations.py --layer l1
```

The default L1 is now `l1-v2.0-<resource-hash>`, using the offline-built expanded
Kenya gazetteer. Existing v1 results remain historical and do **not** satisfy v2
pending checks. The user-authorized forced full v2 run completed on 4 October 2026: 519 fresh
decisions, 17 gated L0 review cases and zero failures. Verified 5 October v2 totals are Kenya
324, not Kenya 35 and ambiguous 160. Sampled validation remains pending; keep future
changed-resource trials bounded before approving another full run.
Select the historical resource explicitly with `--l1-gazetteer v1` when needed.
Rebuild offline with `python3 scripts/build_kenya_gazetteer.py`; verify with `--check`.
Compare without writing annotations:

```bash
python3 scripts/compare_l1_versions.py --limit 20
```

Comparison details remain in ignored `data/trials/processed/`; stdout contains only
aggregates and performance. The comparison enforces a maximum of 20 and offers
`--synthetic` for offline examples. See [v2 specification](docs/annotations.md#18-l1-v2-expanded-offline-geographic-evidence).

Annotation advisory locking requires direct PostgreSQL or the Supabase session
pooler (port 5432). Use that connection for `DATABASE_URL` / `DB_PORT`; the
transaction pooler (6543) is incompatible with session-level locks.

Without a limit, the command considers all matching article versions. By default
it processes only missing current-method results; repeating a completed run adds
no duplicate decisions. L0 uses `valid`, `needs_review`, and `invalid`. L1 runs
only after a current valid L0 and stores `kenya`, `not_kenya`, or `ambiguous` with
evidence and normalized support scores. L1-only execution skips versions without
valid L0 rather than running L0 implicitly. JSON summaries and structured logs
include counts and safe error types, never full article content.

Narrow a run to its recorded collection membership or one article, or explicitly
append a fresh historical decision:

```bash
python3 scripts/run_annotations.py --layer l0,l1 --collection-run-id <uuid> --limit 20
python3 scripts/run_annotations.py --layer l0,l1 --article-id <uuid>
python3 scripts/run_annotations.py --layer l0,l1 --article-id <uuid> --force
```

Open `/annotations`, `/annotations/runs`, `/annotations/l0`, and `/annotations/l1`
to inspect counts, run summaries, source/label-filtered results, and failures.
Article detail pages link historical automated outputs to individual inspection/review
pages. Full article text is available only in an unlocked local Human Review session.
CLI and UI share one annotation service and preserve all earlier rows.

Optional local UI execution requires `ANNOTATION_UI_ENABLED=1`,
`ANNOTATION_UI_TOKEN`, and a distinct `FLASK_SECRET_KEY`, with each secret at least
32 random characters in the ignored `.env`. Restart the app and enter the execution
token in the form. The trigger requires a session CSRF token, accepts only L0/L1,
caps synchronous batches at 20, and requires HTTPS for remote clients. Keep this
disabled on a public deployment until its secrets and trusted HTTPS handling are
configured. For local synchronous UI runs, start Gunicorn with enough time for
the bounded batch:

```bash
gunicorn --timeout 600 -b 127.0.0.1:8080 main:app
```

Use the CLI for full-corpus annotation. See [annotation rules, versioning, and security](docs/annotations.md)
and [actual trial results](docs/roadmap/IMPLEMENTATION_STATUS.md).

## L2 GBV relevance infrastructure

L2 requires the exact current compatible L1 `kenya` result. It has separate
provisional weak labels and installed-model predictions; neither is a human
reference label. L0/L1 validation gates and L2 research validation remain open.
Weak bootstrap covers all 324 eligible versions. The initial development artifact
is configured locally; 324 compatible model predictions are saved and zero eligible versions remain
pending after verified operational closure. Installed L2 schema readiness is true
in development; independent research evaluation remains open. See Section 21 of
[the annotation document](docs/annotations.md#21-l2--gbv-relevance-infrastructure-5-october-2026)
for the model architecture, training procedure and measured operational results.

Apply the new additive migration once to the intended database, after prior
migrations: `migrations/20261005_add_l2_annotations.sql`. Its expected schema objects
were absent in the 5 October development check, despite stored weak labels.
The operational closure installed and behavior-tested the migration in development;
verify other databases independently. Optional local ML dependencies
are in `requirements-l2.txt`.

```bash
# Explicit bounded bootstrap; writes automated weak annotations after migration:
.venv/bin/python scripts/run_annotations.py --layer l2 --l2-mode weak --limit 10
# Pending-only bootstrap over an explicitly agreed full eligible scope:
.venv/bin/python scripts/run_annotations.py --layer l2 --l2-mode weak
# Historical engineering export: original binary weak labels only.
.venv/bin/python scripts/prepare_l2_training_data.py --label-policy weak-only --output-dir data/l2/bootstrap-dev-v1 --limit 20
# Reviewed-only and mixed development exports use exact latest human reviews:
.venv/bin/python scripts/prepare_l2_training_data.py --label-policy reviewed-only --output-dir data/l2/new-reviewed-development
.venv/bin/python scripts/prepare_l2_training_data.py --label-policy mixed-effective --output-dir data/l2/new-mixed-development
# Model inference requires a trained local artifact; no weak/network fallback:
.venv/bin/python scripts/run_annotations.py --layer l2 --limit 10
```

Pending-only weak execution skips existing compatible results; it does not mean
"exactly 324 new articles." Eligibility and pending counts are queried dynamically.

L2 execution now refuses incomplete installed schema before creating run/result rows.
On macOS, model CLI execution automatically holds a scoped `caffeinate` idle-sleep
assertion and releases it on exit. Keep the computer/network available; forced
sleep or lost actual advisory-lock ownership stops writes rather than relocking.
Safe summaries include failure phase, SQLSTATE where available and wall duration.
Resume with the same pending-only command; do not use `--force` for recovery:

```bash
.venv/bin/python scripts/run_annotations.py --layer l2 --l2-mode model
```

Set `L2_MODEL_PATH` to the immutable trained artifact directory and optionally
`L2_MODEL_VERSION` to enforce its manifest version. `L2_POSITIVE_THRESHOLD=0.8`
and `L2_NEGATIVE_THRESHOLD=0.2` are **UNVALIDATED ENGINEERING THRESHOLDS**.
Changing an artifact or thresholds changes current compatibility. Model binaries
belong under ignored `models/artifacts/`; bootstrap text belongs under `data/`.
Training is a separate explicit `scripts/train_l2_classifier.py` action with
configurable model/revision, dataset version, seed, device and `--max-steps`.
The CLI defaults to three epochs and `--class-weighting balanced`; use
`--class-weighting none` to explicitly disable weighting. Balanced weights are
`N / (2 * class_count)`, applied to per-example cross entropy and averaged over
batch examples. `--weight-decay` defaults to 0.01. Reviewed/mixed records retain
human-validation ID/guideline and controlled label provenance. Latest unresolved
or borderline reviews are excluded; mixed mode falls back to weak labels only
for unreviewed binary results. Existing weak-only label selection remains intact; its added `weak_original`
provenance explicitly distinguishes original machine labels from a verified
unreviewed fallback.

Keep dataset outputs immutable: choose a new directory for every export. If a
frozen human reference set is designated, supply `--reference-manifest` to the
reviewed/mixed exporter and check script. It must identify explicit frozen
`human_reference_test` membership through article/version IDs and/or body hashes;
reference records and exact-body duplicates are excluded before storage reads.
No final held-out human reference set is currently frozen; these exports do not
create one, and their records are development data.

After a successful trained-artifact save, verify offline reload and at most 20
real in-memory predictions without inserting annotations:

```bash
.venv/bin/python scripts/check_l2_model.py \
  --model-path models/artifacts/l2-afroxlmr-dev-v1 \
  --output-dir data/l2/new-development-check --limit 20
```

The check disables Hub fallback, verifies installed L2 schema objects read-only,
keeps article text out of output, and saves aggregate diagnostics plus private
review priorities. It never changes human/weak labels or writes predictions.
Schema readiness must be confirmed separately before automated model writes.


The monitor adds `/annotations/l2`, clickable live coverage/labels/pending,
`?mode=weak` bootstrap inspection and exact-lineage detail/history. L2 results
open protected Human Review, including direct unlock, full text and separate review
history. See [L2 specification, commands and limitations](docs/annotations.md#21-l2--gbv-relevance-infrastructure-5-october-2026).

### Local Human Review

Click any L0/L1/L2 count on `/annotations`, filter the result list, then open a row.
The inspection page shows machine evidence and links back to the article. Human
reviews append separate records; corrections preserve the original machine label.
Save & Next stays within the selected layer, label, source and review-status cohort.
For L2, mode and method/model-version filters are also preserved. Human Review
shows separate L2 weak-bootstrap and model-prediction counts; neither inherits a
review from the other. L2 human labels are `gbv`, `not_gbv`, and `borderline`.

Apply the additive migration once, after the earlier migrations:

```bash
psql "$DIRECT_DATABASE_URL" -f migrations/20261004_add_human_validations.sql
# Install the L2 annotation constraints before enabling further automated L2 writes:
psql "$DIRECT_DATABASE_URL" -f migrations/20261005_add_l2_annotations.sql
# After the L2 automated-annotation migration, extend existing review constraints:
psql "$DIRECT_DATABASE_URL" -f migrations/20261005_add_l2_human_validations.sql
```

These commands describe setup for a new database. The human-validation table and
L2 human-validation extension are already installed in development; do not rerun
those migrations blindly. The L2 annotation migration remains a separate prerequisite.
`psql` requires `DIRECT_DATABASE_URL` to be set in the shell environment; Python
entry points load the ignored `.env` themselves. Keep connection values private.

For local review, configure these values in the ignored `.env`, then restart the app:

```dotenv
HUMAN_REVIEW_ENABLED=1
HUMAN_REVIEW_TOKEN=<distinct random secret of at least 32 characters>
FLASK_SECRET_KEY=<random secret of at least 32 characters>
HUMAN_REVIEWER_ID=<actual configured reviewer identity>
HUMAN_REVIEW_GUIDELINE_VERSION=<actual annotation guideline version>
```

Generate each secret separately with `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`.
Open the app at `http://127.0.0.1:8080`, select a result and unlock with the review
token. For bootstrap review, open `/annotations/l2?mode=weak`, select an article,
and unlock directly on its L2 review page. Choose Confirm, Correct, Unable to determine,
or Needs adjudication; use Save Review or Save & Next. The server records the configured identity and guideline version; the browser
cannot choose them. Access lasts 30 minutes and can be locked explicitly. Keep
notes private and avoid unnecessary victim identifiers. All labels are reviewable.

For L2 validation, a successful authorized Preview renews the 30-minute review
window after cloud verification. Management forms use a separate CSRF token from
article-review forms. Reload old forms after app updates. If a creation submission
finds an expired session, unlock again and preview the restored batch settings;
no mutation is replayed automatically. Invalid/stale form tokens remain blocked.

Human Review is disabled by default. Remote/proxied review is blocked even over
HTTPS; this local capability token is not multi-user authentication. Authenticated
reviewer accounts, authorization and trusted HTTPS deployment are required before
remote review. Creating the UI does not complete sampled human validation or the
roadmap exit gates. See [Human Review and Validation](docs/annotations.md#20-human-review-and-validation).

App Engine uses `app.yaml`; required secret/configuration handling is documented in
[`docs/app_engine_deployment.md`](docs/app_engine_deployment.md).

## Running trial data collection

Run all commands from the repository root. The collectors need internet access to
retrieve publisher pages or Internet Archive captures, but the regression tests run
offline against synthetic fixtures.

### 1. Configure infrastructure and dependencies

Python 3 is required. Install the project dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Copy `.env.example` to the ignored `.env` file and configure the database and GCS
variables. Authenticate locally using Application Default Credentials, never a
checked-in service-account key:

```bash
gcloud auth application-default login
python3 scripts/test_infrastructure_connections.py
```

Optionally identify the research crawler with a real project contact address:

```bash
export SCRAPER_USER_AGENT="GBVResearchBot/0.1 (+https://your-project.example; contact@example.com)"
```

Do not copy that placeholder unchanged. If the variable is omitted, the collector
uses its generic default user agent. Requests are sequential, respect robots checks,
retry transient failures, and use a minimum delay of 1.5 seconds.

### 2. Run the offline checks

Verify the parsers before making network requests:

```bash
python3 -m unittest discover -s tests -v
```

### 3. Choose the appropriate collector

Use `scripts/trial_scraper.py` for bounded, cloud-backed historical extraction.
Wayback discovery through `waybackpy` is now the CLI default for every registered
publisher: `nation`, `standard`, `star`, `citizen`, `tuko`, `kenyans`, `taifaleo`.
Publisher modules define domains, prefixes, article routes and extraction adapters.
`scripts/collect_monthly.py` remains the separate retrospective collector with its
existing publication-window and resumable scan contracts.

#### Shared historical Wayback and keyword discovery

In an activated environment, a single-publisher enrichment command is:

```bash
caffeinate -i python scripts/trial_scraper.py \
  --sources nation \
  --term femicide --term rape --term raped --term defilement --term defiled \
  --term "sexual violence" --term "sexual assault" --term "sexual abuse" \
  --term "domestic violence" --term "gender based violence" \
  --term "wife killed" --term "woman killed" --term "female genital mutilation" --term FGM \
  --from-date 2025-01-01 --to-date 2026-09-30 \
  --selection newest --max-records 10000 --max-index-requests 20 --max-pages 20 \
  --limit 200 --max-attempts 1000 --delay 3 \
  --run-name nation_wayback_gbv_expanded
```

For multiple publishers (200 new successful saves **per publisher**, at most 800
for these four), use the same shared flow:

```bash
caffeinate -i python scripts/trial_scraper.py \
  --sources nation standard star citizen \
  --term femicide --term rape --term defilement --term "sexual assault" \
  --term "domestic violence" --term "gender based violence" --term FGM \
  --from-date 2025-01-01 --to-date 2026-09-30 \
  --selection newest --max-records 10000 --max-index-requests 20 --max-pages 20 \
  --limit 200 --max-attempts 1000 --delay 3 \
  --run-name multi_publisher_wayback_gbv
```

Add `tuko kenyans taifaleo` after `--sources` to select their registered adapters.
Repeatable `--source` remains a compatibility alias. Omit source selection to use
all seven. Add `--dry-run` to print the plan without HTTP, cloud credentials or DB
access. Omit `--term` for broad discovery; terms use escaped case-insensitive OR
matching against **original URL text only**, accommodating hyphens and encoded
spaces. They do not search titles/bodies or establish GBV relevance. Relevant
stories without these URL terms can be missed, and English terms can miss Swahili
stories. Keyword enrichment must supplement broad corpus sampling; saved articles
enter the existing separate L0/L1/L2 annotation/classification workflow without
GBV labels being assigned by the collector.

`--from-date`/`--to-date` are inclusive **archive capture dates**, not publication
dates. Optional `--publication-start`/`--publication-end` separately gate parsed
publication dates, excluding missing/unparseable/out-of-window dates after raw
preservation. Capture bounds can miss articles first archived later.

Every publisher receives independent `--max-records` (default 10,000 CDX rows,
including duplicate captures), `--max-index-requests` (20 logical CDX fetches), and
`--max-attempts` (default five times its article save limit) budgets. `--max-pages`
(default 20) additionally caps pages per prefix/URL query. CDX requests ask for at
most 500 remaining records. Shared HTTP retries remain capped at three per request,
with robots checks, allowed-host and redirect validation, finite timeouts and the
configured pacing. Replay requests retain their existing bounded redirect handling.
No unbounded archive enumeration or automatic live fallback is used.

Discovery validates publisher routes and selects one capture per publisher and
normalized original identity. `--selection newest|oldest` compares timestamps
among the **bounded observed captures**; a truncated scan does not establish the
newest/oldest capture in the full archive. Discovery finishes before extraction,
so large bounds may take time even for a small article target. Existing URL and
within-publisher content duplicates, fetch/parse failures and publication exclusions
do not count toward `--limit`. Page/record/request/attempt bounds or available
coverage may prevent reaching the requested number.

Repeat `--url URL` to resolve supplied live article URLs to suitable archived
captures, or supply validated dated replay URLs directly. Captures must be within
the requested date range. Homepages, categories, login routes and unrelated domains
are rejected. Each replay is dispatched to its own publisher parser. Raw HTML,
normalized JSON and run artifacts remain private in GCS; Supabase indexes article,
version and run lineage. Original URL, actual replay URL, capture timestamp and
publication date remain separate.

`No accessible article body` means the parser could not produce an article; it
can indicate an unsupported HTML layout as well as missing/restricted content.
Raw HTML is stored before parsing, but rejected pages receive no normalized
article/version indexing. Citizen parser 1.2 also supports the inspected older
`.article-content .the-content` layout. A running process retains its loaded parser;
later invocations use the correction without needing to stop an ongoing collection.

Console counters and `runs/<run-name>/progress.json` report records, CDX requests,
unique candidates, capture duplicates, stored-article duplicates, extraction
successes, fetch/parse/storage failures and per-source stop reasons. New invocations
also write `trial_report.json`. Empty coverage, failed index requests and configured
bounds are distinct; publisher failures are reported and other sources continue.
`no_valid_candidates` means records were returned but failed route/date/term
validation; it does not mean the publisher has no archived articles. In the actual
seven-publisher smoke, Citizen and Kenyans.co.ke each saved five articles; Nation,
Standard, Star and Tuko hit CDX timeouts. Taifa Leo returned newer section-prefixed
URLs outside its current root-slug/dated-story route support. Archive coverage,
access restrictions and publisher layout changes can therefore prevent collection
even with a registered adapter. See the implementation log for actual counters.
Run configuration pins method, terms, selection, bounds and supplied-URL digest.
Use a fresh run name for changed settings; omitting it generates one. Reruns repeat
discovery and deduplicate stored articles; no durable CDX cursor is persisted.

#### Explicit live and legacy listing paths

```bash
python scripts/trial_scraper.py --sources citizen tuko --method live --limit 5 --delay 3
python scripts/trial_scraper.py --sources nation --method listing --max-pages 3 --limit 5
```

Live monitoring uses source-configured publisher listing pages and source-specific
live extraction, without fabricated archive provenance. It may also receive
repeatable live article `--url` arguments. Current live discovery scans configured
landing pages, rather than exhaustively following every publisher category.
`--method listing` preserves older source snapshot/listing discovery, including
Nation/Standard pagination and the legacy Taifa Leo CDX path. `--wayback` is now a
redundant compatibility alias for the default method; old `--wayback-start` and
`--wayback-end` accept capture bounds as `YYYYMMDD`. The legacy
`--wayback-section` option limits Nation scope only.

For a separate local Nation January–August 2026 collector, use:

```bash
pip install waybackpy==3.0.6 requests
caffeinate -i python scripts/nation_wayback_standalone.py \
  --start 2026-01-01 --end 2026-08-31 \
  --limit 1000 --max-pages 20 --delay 3
```

This script has no app/database/cloud dependencies. It reuses the repository's
Nation parser and shared requests client (so repository parsing dependencies must
also be installed). Local output is ignored under `data/trials/nation-wayback-2026/`:
`raw/`, `articles.jsonl` and `last_run.json`. Raw HTML is retained before parsing;
only parsed articles with publication dates in the requested interval enter JSONL.
Missing/out-of-window dates are counted and excluded. CDX discovery scans captures
month by month in that same interval, at most 20 pages of 500 rows per month;
articles captured only later may be missed. Capture dates never substitute for
publication dates. CDX failures/page bounds report incomplete coverage and exit 2.
The article save limit yields `limit_reached`, also incomplete coverage. Reruns
revisit discovery and deduplicate stored canonical URLs/content; no cursor is
persisted. Use a separate `--output` directory under `data/` for changed date scopes.
`last_run.json` describes the latest invocation. Paywalls and access restrictions
remain respected; candidate articles still require research quality review.

For archive lookup from pasted public Nation URLs, install the optional operator
dependency with `pip install waybackpy==3.0.6 requests` in the activated environment,
then run `python scripts/collect_wayback_urls.py --run-name nation-wayback-urls-v1`.
Paste URLs/a Markdown table and press **Ctrl-D**, or pass `--file
data/trials/nation-urls.txt`. Default `--selection newest` finds one successful HTML
capture per URL; `--selection oldest` selects the earliest. `--dry-run` validates
input without network/cloud access. Sign-in URLs are rejected. The adapter uses
waybackpy CDX parsing with the shared requests-based, paced, robots-aware HTTP
client, then existing private cloud collection. Archive lookup still depends on
CDX availability and does not bypass paywalls. An accessible capture is not
guaranteed; manually selected inputs remain diagnostic candidates. A changed
resolved capture list requires a new run name; reruns requery CDX. No Save Page Now
requests are issued.

For explicit Nation article URLs, run `python scripts/collect_urls.py --run-name
nation-manual-urls-v1`, paste plain URLs or a Markdown table and press **Ctrl-D**.
Alternatively use `--file data/trials/nation-urls.txt` or repeat `--url URL`.
Add `--dry-run` to validate without any network/cloud access. URL files are private
research material and must stay under ignored `data/`. The script accepts public
live Nation article URLs and dated Wayback article replay URLs. Sign-in routes
(including `redirect_to` links) are rejected without following their embedded
targets; premium/active paywall articles remain inaccessible. It uses existing
robots checks, pacing, parser, private GCS/Supabase storage and deduplication.
Use a new run name for a changed input list. No CDX discovery is performed.
Manually selected/keyword-discovered articles remain diagnostic candidates and
must not substitute for the broad research sampling frame.

To expand Nation beyond its configured archived Kenya homepage (activated environment):

```bash
caffeinate -i python scripts/trial_scraper.py \
  --source nation \
  --limit 1000 \
  --max-pages 100 \
  --delay 3 \
  --method listing \
  --run-name nation-expanded-listings-v1
```

Nation follows linked archived Kenya sections and `?page=N` pagination, bounded
to 100 listing requests and up to 1,000 new saves here. Existing articles are
skipped. Inaccessible listings fail the run while preserving prior saves; linked
pages remaining at the page bound are logged. Matching reruns revisit the homepage
without a durable listing cursor. Use a new run name when changing limits.
Actual discovery provenance is retained after capture redirects. Historical
candidates require publication-date and extraction review before research
inclusion; 1,000 saves are not guaranteed. This expansion does not use CDX.

Use these commands to collect a small, two-article trial from each configured
publisher snapshot with `--method listing`:

```bash
python3 scripts/trial_scraper.py --source nation --limit 2
python3 scripts/trial_scraper.py --source citizen --limit 2
python3 scripts/trial_scraper.py --source standard --limit 2
python3 scripts/trial_scraper.py --source star --limit 2
python3 scripts/trial_scraper.py --source tuko --limit 2
python3 scripts/trial_scraper.py --source kenyans --limit 2
python3 scripts/trial_scraper.py --source taifaleo --limit 2
```

#### Taifa Leo CDX trial (local output)

The `taifaleo` source uses the supplied bounded [Taifa Leo CDX query](https://web.archive.org/cdx/search/cdx?url=taifaleo.nation.co.ke/*&output=json&fl=timestamp,original,statuscode,mimetype&filter=statuscode:200&filter=mimetype:text/html&collapse=urlkey&limit=500).
It discovers successful HTML captures across all available years, without GBV
keywords. The first 500 results are a deterministic archive sample, not a random
sample, a complete archive, or a January 2026 publication dataset.

Run the local two-article trial from any working directory using the script path:

```bash
cd /Users/mutua/Documents/Projects/gbv-news-ai
source .venv/bin/activate
python3 scrapers/wayback.py \
  --sources taifaleo \
  --all-dates \
  --limit 500 \
  --max-articles 2 \
  --max-fetches 2
```

`--all-dates` omits CDX capture-date bounds and cannot be combined with `--end`.
`--limit` caps CDX rows; `--max-articles` caps new saved articles per publisher;
`--max-fetches` caps snapshot retrieval attempts per publisher (each may retry up
to three times). Cached snapshots do not consume retrieval attempts. Fewer than
two articles may be saved. The default output roots are anchored to the repository:

```text
data/trials/raw/taifaleo/<snapshot-hash>.html
data/trials/raw/taifaleo/<snapshot-hash>.meta.json
data/trials/processed/taifaleo.jsonl
data/trials/processed/taifaleo.manifest.json
```

The JSON sidecar retains the requested and actual replay URLs, HTTP status, and
retrieval time. Records retain the publisher parser version, capture timestamp,
publication date, source URLs, content hash, and raw snapshot path. Repeat the
command to skip stored canonical URLs/content and reuse raw snapshots with
metadata. The manifest records new saves and stop/failure counters for the latest
invocation; the JSONL may also contain earlier trial records. Index failures exit
`2` and are not reported as successful empty coverage. All local output is ignored
by Git and requires quality review before research use.

Taifa Leo has root-level WordPress story slugs and `/YYYY/MM/DD/<slug>/` stories.
The publisher parser supports the inspected legacy `.news-details-layout1` body,
visible date and reporter byline, `.entry-content`/structured article metadata, and
the newer `.article-content__content` layout with publisher date metadata. The
current parser version is `taifaleo-archive-1.1`.
Day-only dates retain unknown timezones and day precision. The legacy template
reports `en-US` despite Swahili prose: that metadata is preserved separately,
article language remains unknown, and language review is required. No language
label or Kenya relevance is inferred solely from the publisher.

Taifa Leo uses the shared robots-aware, redirect-restricted client and its own
parser in this local helper. The older six helper paths retain their generic
experimental parser and are not the recommended cloud/monthly collection route.

For GCS/Supabase storage, apply the Taifa Leo migration above before running:

```bash
python3 scripts/trial_scraper.py --source taifaleo --limit 2 --run-name taifaleo-cdx-smoke
```

With `--method listing --max-pages 1`, the legacy cloud trial requests one 500-row CDX batch. To discover beyond that
first batch, increase `--max-pages`; the cloud collector follows CDX continuation
keys and deduplicates article URLs across pages. The standalone local helper above
still requests a single batch.

#### Expand Taifa Leo cloud collection beyond 500 rows

```bash
cd /Users/mutua/Documents/Projects/gbv-news-ai
caffeinate -i .venv/bin/python scripts/trial_scraper.py \
  --source taifaleo \
  --limit 2000 \
  --max-pages 20 \
  --delay 3 \
  --run-name taifaleo-expanded-cdx-v1
```

This requests up to 20 index pages of 500 rows each and saves up to 2,000 new
articles per invocation in private GCS/Supabase. Index rows can include non-article
URLs; already indexed URLs/content, inaccessible captures and parsing failures
reduce new saves. Discovery stops at the save/attempt limits or available index
pages, so 2,000 saves are not guaranteed. A continuation at the page bound produces
a warning; a failed index page fails the run while preserving earlier saves.

Use a new run name when changing limits or page settings. Repeating a matching
run skips indexed duplicates but starts discovery from the first index page;
this trial collector does not persist a CDX continuation cursor. Discovery spans
all available capture years. Review publication dates and extraction quality
before admitting any article to the research corpus.

Monthly collection also accepts `--source taifaleo` and uses that collector's
capture-month and publication-date filters. New default all-source runs include
Taifa Leo. To resume older six-source runs, explicitly select the original six
sources so the saved configuration continues to match.

#### Per-publisher monthly smoke tests

The following bounded commands test January 2026 archive collection. Run all six
publishers sequentially from the repository root with:

```bash
cd /Users/mutua/Documents/Projects/gbv-news-ai
source .venv/bin/activate

for source in nation citizen standard star tuko kenyans; do
  python3 scripts/collect_monthly.py \
    --start-month 2026-01 \
    --end-month 2026-01 \
    --source "$source" \
    --max-index-pages 1 \
    --max-fetches-per-month 2 \
    --run-name "${source}-jan-2026-smoke"
done
```

#### Try the Wayback helper's discovery and original HTML approach

The monthly collector already uses CDX discovery. Two optional settings adopt the
useful parts of the standalone `scrapers/wayback.py` experiment while retaining
publisher-specific parsing, publication-date filtering, robots checks, private GCS
storage, and Supabase lineage:

- `--index-match prefix` queries `<publisher-domain>/*`, as the helper does.
  [CDX documents this as prefix matching](https://github.com/internetarchive/wayback/tree/master/wayback-cdx-server#url-match-scope),
  whereas the existing domain query also includes subdomains. This changes discovery
  scope; faster responses or better coverage have not been established by a live test.
- `--replay-mode original` requests `.../<timestamp>id_/<original-url>` for original
  HTML without Wayback's URL rewriting. Publisher parsers accept both replay formats
  and retain the actual replay URL and capture timestamp if Wayback redirects.

To try these settings for the four original publishers, use a new run name:

```bash
cd /Users/mutua/Documents/Projects/gbv-news-ai
source .venv/bin/activate

for source in nation citizen standard star; do
  python3 scripts/collect_monthly.py \
    --start-month 2026-01 \
    --end-month 2026-01 \
    --source "$source" \
    --index-match prefix \
    --replay-mode original \
    --max-index-pages 1 \
    --max-fetches-per-month 2 \
    --run-name "${source}-jan-2026-wayback-smoke"
done
```

The limit is two article retrieval attempts per source, not two guaranteed saved
articles. CDX returns at most 1,000 rows per index request; a single page may contain
no supported article candidates. January captures are scanned, and only articles
with January publication metadata are saved. Articles published in January but
first captured later require a wider capture window.

Omitting the new options preserves the existing domain/rewritten replay settings
and allows old commands to resume. Repeat all options exactly to resume a new run;
changing either option requires a different run name. Stored articles remain
deduplicated across runs, so an already stored article may be skipped in this trial.
The loop is sequential and intentionally continues when an incomplete smoke test
exits with code `2`. Inspect the scan status and log to distinguish configured limits
from retrieval failures. Infrastructure setup above is still required; these runs
write to GCS and Supabase.

The shared HTTP client now retries HTTP 429 and transient server errors up to three
attempts. It honors valid `Retry-After` seconds or dates. A requested wait exceeding
60 seconds defers that request as a failure instead of retrying early; resume later.

The standalone helper remains exploratory: its date bounds concern archive capture
dates, `--months` approximates months as 30 days, and its single capped CDX query does
not paginate. CDX failures become empty result lists and the helper exits `0`, so
zero output cannot be interpreted as successful empty coverage. Its generic
whole-page paragraph fallback can include unrelated text,
and its HTTP helper lacks the main collector's robots and redirect validation.
It writes relative local paths, which explains the existing `scrapers/data/` output
when launched from that directory. That legacy output is now ignored by Git; the
monthly collector continues to use private GCS and Supabase.

To run or repeat publishers individually, use:

```bash
# Nation
python3 scripts/collect_monthly.py \
  --start-month 2026-01 \
  --end-month 2026-01 \
  --source nation \
  --max-index-pages 1 \
  --max-fetches-per-month 2 \
  --run-name nation-jan-2026-smoke

# Citizen
python3 scripts/collect_monthly.py \
  --start-month 2026-01 \
  --end-month 2026-01 \
  --source citizen \
  --max-index-pages 1 \
  --max-fetches-per-month 2 \
  --run-name citizen-jan-2026-smoke

# Standard
python3 scripts/collect_monthly.py \
  --start-month 2026-01 \
  --end-month 2026-01 \
  --source standard \
  --max-index-pages 1 \
  --max-fetches-per-month 2 \
  --run-name standard-jan-2026-smoke

# Star
python3 scripts/collect_monthly.py \
  --start-month 2026-01 \
  --end-month 2026-01 \
  --source star \
  --max-index-pages 1 \
  --max-fetches-per-month 2 \
  --run-name star-jan-2026-smoke
```

These are smoke tests, not complete monthly collection runs. The index-page and
article-fetch limits intentionally produce incomplete coverage. Use new run names if
you later remove either limit for complete January collection.

To smoke-test the two newer sources against August 2026 archive coverage:

```bash
# Tuko
python3 scripts/collect_monthly.py \
  --start-month 2026-08 \
  --end-month 2026-08 \
  --source tuko \
  --max-index-pages 1 \
  --max-fetches-per-month 2 \
  --run-name tuko-aug-smoke

# Kenyans.co.ke
python3 scripts/collect_monthly.py \
  --start-month 2026-08 \
  --end-month 2026-08 \
  --source kenyans \
  --max-index-pages 1 \
  --max-fetches-per-month 2 \
  --run-name kenyans-aug-smoke
```

The Wayback CDX index contains Kenyans.co.ke `/news/` captures in August 2026, so
August is a valid smoke-test month even though its configured single-snapshot trial
seed is from July 2024.

Before starting the full monthly collection, run a bounded smoke test with a new,
descriptive run name:

```bash
python3 scripts/collect_monthly.py \
  --start-month 2026-08 --end-month 2026-08 \
  --source citizen \
  --max-index-pages 1 --max-fetches-per-month 2 \
  --run-name citizen-aug-smoke
```

The two limits apply to each publisher/capture-month scan. A limited smoke test is
reported as incomplete coverage; that is expected. Use a different run name for
the full collection because saved runs can only resume with exactly the same dates,
sources, delay, and limits.

### 4. Inspect the results

The collectors keep object payloads in private GCS buckets and structured lineage in
Supabase:

```text
gs://<GCS_RAW_BUCKET>/<source>/<capture-year>/<capture-month>/<article-id>/<raw-content-hash>.html
gs://<GCS_PROCESSED_BUCKET>/<parser-version>/<source>/<publication-year>/<publication-month>/<article-id>/<content-hash>.json
gs://<GCS_RUNS_BUCKET>/runs/<run-name>/progress.json
gs://<GCS_RUNS_BUCKET>/runs/<run-name>/monthly_counts.csv
gs://<GCS_RUNS_BUCKET>/runs/<run-name>/collection.log
gs://<GCS_RUNS_BUCKET>/runs/<run-name>/cdx-cache/<request-hash>.cdx.json
```

Open several processed JSON records and compare `article_text`, title, author,
publication date, canonical URL, and source against their raw HTML. Also review
`kenya_relevance`, which intentionally begins as `needs_review`. Counts represent
unreviewed news candidates, not confirmed GBV articles or incidents.

For a monthly run, inspect its durable progress and log with:

```bash
gcloud storage cat gs://gbv-news-ai-runs/runs/citizen-aug-smoke/progress.json
gcloud storage cat gs://gbv-news-ai-runs/runs/citizen-aug-smoke/collection.log
```

Replace the example directory with the run name you selected. You can stop a run
with Ctrl-C; progress is written before exit.

### 5. Resume or diagnose a monthly run

Rerun the exact same monthly command with the same `--run-name` to resume. Completed
scans and existing articles are skipped, cached CDX discovery responses are reused,
and stored canonical URLs and content hashes prevent duplicate insertion. Never run
two collector processes against the same run name; a PostgreSQL advisory lock rejects it.

Check `progress.json` and `collection.log` when a run exits non-zero. Common scan
states include:

- `index_exhausted`: the available archive index was scanned successfully.
- `index_exhausted_with_gaps`: scanning finished, but some articles failed or lacked dates.
- `fetch_limit` or `index_page_limit`: a configured smoke-test limit was reached.
- `index_failed`: the archive index request failed or returned an invalid response.
- `paused_index_unavailable`: three consecutive index failures paused the run safely.

A failed or pending scan does not mean that the publisher released no articles. The
Wayback index is incomplete by nature, and inaccessible, restricted, malformed, or
undated pages are not stored as valid article records.

The CDX read timeout defaults to 30 seconds per attempt. For slow index responses,
add `--index-read-timeout 120` (accepted range: 1–300 seconds). This is an operational
setting: it may change while resuming the same run name without changing dates,
sources, query scope, delay or limits. Each invocation records its timeout and UTC
start time in `progress.json` under `execution_settings`, and logs the timeout.
Connect timeout remains 10 seconds; robots and article-replay read timeouts remain
30 seconds. Requests still have at most three attempts; 120-second index waits
can therefore take roughly six minutes per failed query, plus connect/retry time.

Repeated CDX timeouts or HTTP 504 responses mean index discovery is unavailable for
that scan. After three consecutive index failures the run saves progress and exits
as `paused_index_unavailable`. A longer client timeout cannot repair an upstream
gateway failure. Stop repeated immediate retries and resume later with the same
run/configuration. These states are incomplete coverage, not zero publisher output.

To retry the six-publisher expansion with a longer index wait:

```bash
caffeinate -i .venv/bin/python scripts/collect_monthly.py \
  --start-month 2026-01 --end-month 2026-08 \
  --source nation --source standard --source star \
  --source citizen --source taifaleo --source tuko \
  --delay 3 --index-read-timeout 120 \
  --max-index-pages 0 --max-fetches-per-month 0 \
  --run-name six-publisher-jan-aug-2026-expansion-v1
```

Run one process at a time. `caffeinate` prevents macOS idle sleep while the command
runs; it does not prevent network failures or forced sleep. This collection example
includes Tuko for development; the finalized codebook and draft sampling protocol specify the formal study scope.

## January–August 2026 collection

The monthly collector scans all seven registered publishers from August back to January 2026,
without GBV keyword filtering. It filters by article publication date and writes
per-publisher, per-month counts, including explicit failed and pending scan states.

```bash
python3 scripts/collect_monthly.py \
  --start-month 2026-01 --end-month 2026-08 \
  --run-name jan-aug-2026
```

Monthly counts, progress, logs, and cached discovery live below
`gs://<GCS_RUNS_BUCKET>/runs/jan-aug-2026/`. Rerunning the same command resumes from
GCS and Supabase. This run has no article cap and may take substantial time.
See [the collection protocol](docs/collection_protocol.md) for sampling, test limits,
resume behavior, and archive coverage limitations. The 5,000 target concerns fully
annotated articles, not a cap on raw collection.

### Storage and Git safety

Real collection output is durable only in private GCS and Supabase; collectors do not
write it below `data/`. Existing Git exclusions remain defense in depth for legacy or
downloaded artifacts. Never commit credentials, ADC files, or collected content.

```bash
git status --short
git ls-files data
```

The second command should list only intentional `README.md` and `.gitkeep` files, if
any. Test fixtures under `tests/fixtures/` are small, synthetic regression inputs and
may remain tracked; they are not collected research data.

## Upload existing local trials to GCS and Supabase

`scripts/import_local_trials.py` imports publisher JSONL files and individual article
JSON files with their raw HTML, without fetching publishers again or deleting local
files. It uses the
same GCS/Supabase configuration as the cloud collectors. Apply the source migrations
above before uploading, including the Taifa Leo migration where applicable.

Preview local files without cloud access:

```bash
python3 scripts/import_local_trials.py --run-name all-local-trials --dry-run
```

Upload from the default `data/trials/processed/` and `data/trials/raw/` roots:

```bash
python3 scripts/import_local_trials.py --run-name all-local-trials
```

For legacy trials saved beneath `scrapers/data/`, use a separate run name:

```bash
python3 scripts/import_local_trials.py \
  --processed-root scrapers/data/trials/processed \
  --raw-root scrapers/data/trials/raw \
  --run-name legacy-local-import-v2 --dry-run
```

Remove `--dry-run` from that command to upload. Repeat `--source citizen` or another
registered source to select publishers; otherwise all supported article records
in the selected processed root are imported. JSONL files use publisher filenames;
individual JSON articles declare their `source` inside the record. Both formats
are read directly from the processed root. Manifests and non-article JSON are
excluded. Raw paths may use either `raw_snapshot_path` or the older `raw_snapshot`
field. Run from the repository root when supplying relative paths.

The importer verifies publisher URLs, required fields, collection timestamps,
article-text hashes, and raw snapshots before writing. Raw files must resolve
inside the selected raw root. Older generic Wayback records without a raw path
are matched using their original replay filename. They retain their experimental
parser version; importing does not reparse or validate extraction quality.

Uploads skip stored URLs and within-publisher content hashes, including duplicates
in the input. Create-only, content-addressed GCS objects and transactional database
constraints protect identical retries. Existing URLs are skipped rather than used
to replace cloud records. A local-import advisory lock prevents simultaneous imports;
avoid concurrent collection while migrating local trials.

Rerun the same command after a partial failure. Durable objects are reused and
database indexing is retried; local input must remain unchanged for identical
retries. Changing roots, source selections, or supported input formats requires a
new run name. Older JSONL-only importer runs therefore need a new run name such as
`all-local-trials` with this version. A dry run
checks only local files and local duplicates; it does not check cloud duplicates.

The terminal summary reports checked, ready (preview only), saved, duplicate, and
failed records, with source/file/line/error-type references. Exit code `2` indicates
failures. Cloud uploads save the latest summary at
`gs://<GCS_RUNS_BUCKET>/runs/<run-name>/import_summary.json` and update the run status
in Supabase. Uploaded metadata appears in the read-only monitor. Imported articles
remain unreviewed trials, and missing/uncertain publication dates remain flagged.

## Single-snapshot trial data collection

The trial scraper discovers news candidates from Daily Nation, Citizen Digital,
The Standard, The Star, Tuko, Kenyans.co.ke, and Taifa Leo. Optional `--term` filters original URL text; no GBV labels are assigned.
Publisher-specific URL rules and body selectors live in `scrapers/`; shared HTTP
and metadata handling lives in `scrapers/common.py`.

```bash
python3 scripts/trial_scraper.py --source standard --limit 5
```

Repeat `--source` to select multiple publishers, or omit it to try all seven.
`--limit` caps new records per publisher; retrieval attempts are capped at five
times that limit. `--delay` defaults to two seconds and cannot be below 1.5 seconds.
Optionally set `SCRAPER_USER_AGENT` to an honest research-bot identity with your
actual project contact information. No placeholder contact address is sent.

Under `--method listing`, the `nation` option uses the supplied [archived Daily Nation Kenya homepage](https://web.archive.org/web/20240616131714/https://nation.africa/kenya/).
It discovers reporting across news, counties, business, sports, lifestyle, health,
weekly review, and opinion sections. Records identify `publisher_name: "Daily Nation"`
and `content_scope: "news_reporting"`. Explicitly premium-labelled links and articles,
and active paywalls, are skipped. Nation's inactive hidden paywall template does not
by itself mark an otherwise accessible article as restricted.
The earlier corporate-news trial record remains preserved with its original
`content_scope: "corporate_news"`; exclude it when selecting Daily Nation reporting.
Linked section/pagination pages are followed within the listing budget, without a
fallback to the live publisher. Wayback may redirect an article to a nearby capture;
records retain its actual `archive_url` and `archive_capture_timestamp` separately
from the original URL and publication date. For example:

```bash
python3 scripts/trial_scraper.py --source nation --limit 5
```

Under `--method listing`, the `star` option uses the supplied [archived Star homepage](https://web.archive.org/web/20251227053140/https://www.the-star.co.ke/).
It follows dated article links across news, counties, business, sports, health,
lifestyle, politics, opinion, and climate coverage on that snapshot. Kenya relevance
remains subject to review, including international reporting on the homepage.
Archive requests validate both the archive host and the embedded publisher domain;
redirects to live publishers or other publishers' snapshots are rejected.
Star records preserve original URLs, actual archive capture timestamps, and visible
publication dates. When the visible publication time has no timezone, the record
sets `publication_timezone: "unknown"`. Raw Star pages use the `star/<year>/<month>/`
prefix in the configured raw GCS bucket.

```bash
python3 scripts/trial_scraper.py --source star --limit 5
```

Under `--method listing`, the `citizen` option uses the supplied [archived Citizen Digital homepage](https://web.archive.org/web/20260304002240/https://citizen.digital/).
It accepts the snapshot's `/article/` links and supported section URLs ending in
`-n<article-id>`. The parser handles HTML-escaped structured metadata and nested
names in author fields, and extracts the article body from Citizen's content container.
Original publisher URLs, the discovery snapshot, and the actual article capture are
stored separately. An archived article may redirect to a capture on a different day;
these records are not guaranteed to reproduce the homepage's exact point in time.
Publication times without an explicit timezone are marked `publication_timezone: "unknown"`.
Raw Citizen pages use the `citizen/<year>/<month>/` prefix in the raw GCS bucket.

```bash
python3 scripts/trial_scraper.py --source citizen --limit 5
```

Under `--method listing`, the `standard` option uses the supplied [archived Standard homepage](https://web.archive.org/web/20200812220501/https://standardmedia.co.ke/).
To expand beyond the homepage, set `--max-pages`. For Standard this caps listing
fetch attempts including the homepage; pass one for the original single-page trial. Taifa Leo uses the same
option for CDX index pages, as described above.
The scraper follows linked category pages and `?page=N` pagination when present,
visits listings breadth-first, and interleaves their article links before retrieval.
Domestic category links are prioritized deterministically. Duplicate article URLs
are skipped across listings. Discovery finishes within the page budget before
article retrieval starts, so larger page budgets take longer even with small limits.

```bash
python3 scripts/trial_scraper.py --source standard --max-pages 3 --limit 5
```

The inspected homepage had 49 article links. Its National category page yielded
39 additional URLs beyond the homepage. These are discovery counts, not guarantees
that every linked article has an accessible archived body. Raw Standard articles use
the `standard/<year>/<month>/` GCS prefix; records retain the discovery listing URL.
Standard's 2020 body layout requires extraction of direct text nodes as well as
paragraphs, with related links, image captions, and embedded charts removed.
Explicit EAT publication timestamps are normalized to UTC+03:00.
This single-snapshot command follows pages from the supplied snapshot. Use the
monthly collector above for the January–August 2026 archive window.

Under `--method listing`, the `tuko` option uses the supplied [archived Tuko homepage](https://web.archive.org/web/20260831023500/https://www.tuko.co.ke/).
It accepts publisher-hosted story paths containing a numeric article ID beneath one
to three section components, for example `/kenya/638082-story/` and
`/people/family/638077-story/`. Section, tag, author, and navigation URLs are rejected.
The inspected layout exposes JSON-LD metadata and article prose in `.post__content`;
promotional calls to action, related-story cards, advertisements, and figure captions
are removed. Records use parser version `tuko-archive-1.0`.

```bash
python3 scripts/trial_scraper.py --source tuko --limit 2
```

Under `--method listing`, the `kenyans` option uses the supplied [archived Kenyans.co.ke homepage](https://web.archive.org/web/20240725032840/https://www.kenyans.co.ke/).
It accepts only `/news/<numeric-id>-<slug>` stories, excluding `/news`, tracker,
featured, author, and other non-article routes. The inspected Drupal layout provides
JSON-LD title, author, and date metadata and stores prose in the news-body field.
Records use parser version `kenyans-archive-1.0`. August 2026 CDX inspection found
archived `/news/` stories, although Wayback coverage remains non-exhaustive.

```bash
python3 scripts/trial_scraper.py --source kenyans --limit 2
```

Discovery is bounded CDX enumeration by default, or configured pages in explicit live/listing mode; it is not a complete archive.
The parser uses structured article metadata or publisher body containers.
The supplied homepages for the original six publishers and linked archived articles were checked
successfully during development. Other pages and publishers still require live quality
review; the offline fixtures are synthetic and do not establish complete compatibility.

Requests check robots.txt, validate publisher domains before following redirects,
use timeouts, and retry transient network/server failures. Access denials and
unverifiable robots policies are skipped. Detected paywalled articles are skipped.
A run may therefore collect fewer articles than requested, including zero.

Raw snapshots are written to GCS before parsing. Normalized JSON then goes to the
processed bucket, followed by transactional article/version indexing in Supabase.
Records preserve canonical/requested URLs, dates, hashes, parser and discovery
provenance, GCS URIs and generations, and run linkage. Supabase supplies URL/hash
deduplication; create-only object writes prevent silent replacement.

All articles start with `kenya_relevance: "needs_review"`: a Kenyan publisher can
also cover international news. Domestic sections narrow discovery, but are not proof
of geographic relevance. Review relevance, article-body completeness, dates, and
language before promoting any trial data. Unknown language stays empty; missing
publication dates are flagged. No final research corpus has been validated.

Run offline regression checks with:

```bash
python3 -m unittest discover -s tests -v
```


### Collection run filtering, Stop and orphan recovery

The collection Runs page supports `/runs?status=running` and other persisted
status filters, pagination, worker heartbeat/elapsed display and opt-in protected
cooperative Stop. Annotation runs retain their separate controls. Updated workers
require `migrations/20261008_add_collection_run_control.sql`; install it in filename
order before starting them and restart the monitor. Never assume it is installed
on every target.

Enable Stop with private `COLLECTION_CONTROL_ENABLED=1`, a strong
`COLLECTION_CONTROL_TOKEN`, and `FLASK_SECRET_KEY`. Stop uses POST, token and
signed-session CSRF; it requests cancellation rather than killing a process.
Completed work survives; the worker checkpoints and ends as `interrupted`.
Older workers cannot honor Stop and are shown without that control. Exact-config
same-name resume remains supported.

Heartbeat writes occur at most every 30 seconds at worker checkpoints; page loads
never renew them. `Possibly stalled` is informational. Diagnose with
`.venv/bin/python scripts/reconcile_runs.py --dry-run`; explicit `--apply` repairs
only managed attempts with stale heartbeat and a provably unowned collector lock.
Legacy missing-heartbeat rows remain unchanged. See
[collection run control and recovery](docs/collection_run_control.md) for migration,
status semantics, security, cancellation latency, reconciliation and limitations.


### Git push readiness

The 8 October GitHub dry-run push succeeded; the user confirmed no current error.
Main subsequently advanced to `25342a7` and matches `origin/main`; the Runs
changes are committed, while this new Markdown alignment remains uncommitted. Review and commit intended source/documentation before pushing; Git
push does not publish uncommitted files. See [the diagnostic and safe steps](docs/git_push_diagnostic.md).
