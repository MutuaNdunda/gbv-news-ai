# GBV News AI

GBV News AI is a postgraduate research project that aims to develop an ethical, human-supervised system for identifying, classifying, geotagging, and mapping gender-based violence (GBV) reporting in Kenyan digital news. The planned system will investigate multilingual approaches for English, Swahili, Sheng, and code-switched content, where available.

The collection pipeline and automated L0 extraction-quality / L1 Kenya-relevance
layers are operational. L2 weak supervision, training/inference infrastructure and
protected local L0/L1/L2 Human Review are implemented. No validated final research
dataset is available yet. The roadmap now records 536 article versions; its older
407-record figure was a planning snapshot. Automated results still require sampled
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

## Current progress — verified 6 October 2026, 00:04 EAT

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

L2 operational closure verifies **324/324 compatible Transformer predictions**:
**11 gbv / 307 not_gbv / 6 borderline**, with **zero pending**. The additive L2
migration is installed and behavior-tested in development. Pending-only resume
added 24 predictions without changing existing model, weak, human or L1 history.
The earlier interrupted run coincided with macOS idle sleep; model CLI runs now
prevent idle sleep and verify actual advisory-lock ownership before writes.
See [the L2 performance report](docs/l2_model_performance.md) for the diagnosis,
timing and remaining limitations. Original weak outputs remain separately
inspectable at `/annotations/l2?mode=weak`. Full offline suite including the
installed-model integration: **275 tests passed**, zero skips. See
[the engineering log](docs/roadmap/IMPLEMENTATION_STATUS.md) for execution evidence.
L0 remains 519 valid / 17 needs_review; L1 v2 324 kenya / 35 not_kenya /
160 ambiguous. Independent research validation and L3–L5 remain pending. The proposed next
implementation is reproducible human-validation batches, initially hidden model
output, adjudication and progress reporting in the existing local review workspace.
Agree the codebook and sampling protocol first; see
[the planned validation milestone](docs/annotations.md#17-next-steps-future-work).
These additions are not yet implemented.

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
The last successful sync on 5 October records completed model training and
pre-closure 300/324 coverage; the later 6 October verification records 324/324.
This documentation update did not resynchronize or change the public Sheet.
Independent evaluation remains pending; synchronized CSVs are not manually edited.
See [the roadmap workflow](docs/roadmap/README.md) and
[implementation status](docs/roadmap/IMPLEMENTATION_STATUS.md).

## Corpus Collection Monitor

The implemented Flask monitor provides a read-only operational view of collection state.
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

Stop either server with Ctrl-C. The monitor has no collection controls; annotation
execution is disabled by default. If startup or `/health` fails, rerun
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

Use `scripts/trial_scraper.py` for a quick, bounded extraction-quality sample from
the configured publisher snapshots or Taifa Leo's supplied CDX query. Use `scripts/collect_monthly.py` for the
January–August 2026 retrospective corpus. Neither collector applies GBV keywords or
produces GBV labels.

For a local Taifa Leo archive trial without cloud/database writes, use the command
in the Taifa Leo subsection below. For a cloud end-to-end check, collect up to two Citizen articles:

```bash
python3 scripts/trial_scraper.py --source citizen --limit 2 --run-name trial-citizen-smoke
```

To sample all seven publishers, omit `--source`:

```bash
python3 scripts/trial_scraper.py --limit 5
```

`--limit` applies separately to each selected publisher. Repeat `--source` to select
several publishers, and use `--delay` to increase the request interval:

```bash
python3 scripts/trial_scraper.py \
  --source nation --source citizen --limit 5 --delay 3
```

For Standard only, `--max-pages` controls how many archive listing pages are scanned,
including the homepage:

```bash
python3 scripts/trial_scraper.py \
  --source standard --max-pages 3 --limit 5
```

#### Per-publisher trial commands

Use these commands to collect a small, two-article trial from each configured
publisher snapshot:

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

This cloud trial uses one 500-row CDX batch too; `--max-pages` does not expand it.
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
The Standard, The Star, Tuko, Kenyans.co.ke, and Taifa Leo. It does not filter by GBV keywords
or assign GBV labels.
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

The `nation` option uses the supplied [archived Daily Nation Kenya homepage](https://web.archive.org/web/20240616131714/https://nation.africa/kenya/).
It discovers reporting across news, counties, business, sports, lifestyle, health,
weekly review, and opinion sections. Records identify `publisher_name: "Daily Nation"`
and `content_scope: "news_reporting"`. Explicitly premium-labelled links and articles,
and active paywalls, are skipped. Nation's inactive hidden paywall template does not
by itself mark an otherwise accessible article as restricted.
The earlier corporate-news trial record remains preserved with its original
`content_scope: "corporate_news"`; exclude it when selecting Daily Nation reporting.
Only article links on that archived listing are followed, without pagination or a
fallback to the live publisher. Wayback may redirect an article to a nearby capture;
records retain its actual `archive_url` and `archive_capture_timestamp` separately
from the original URL and publication date. For example:

```bash
python3 scripts/trial_scraper.py --source nation --limit 5
```

The `star` option uses the supplied [archived Star homepage](https://web.archive.org/web/20251227053140/https://www.the-star.co.ke/).
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

The `citizen` option uses the supplied [archived Citizen Digital homepage](https://web.archive.org/web/20260304002240/https://citizen.digital/).
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

The `standard` option uses the supplied [archived Standard homepage](https://web.archive.org/web/20200812220501/https://standardmedia.co.ke/).
To expand beyond the homepage, set `--max-pages` (currently supported for Standard
only). This caps listing fetch attempts including the homepage; the default is one.
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

The `tuko` option uses the supplied [archived Tuko homepage](https://web.archive.org/web/20260831023500/https://www.tuko.co.ke/).
It accepts publisher-hosted story paths containing a numeric article ID beneath one
to three section components, for example `/kenya/638082-story/` and
`/people/family/638077-story/`. Section, tag, author, and navigation URLs are rejected.
The inspected layout exposes JSON-LD metadata and article prose in `.post__content`;
promotional calls to action, related-story cards, advertisements, and figure captions
are removed. Records use parser version `tuko-archive-1.0`.

```bash
python3 scripts/trial_scraper.py --source tuko --limit 2
```

The `kenyans` option uses the supplied [archived Kenyans.co.ke homepage](https://web.archive.org/web/20240725032840/https://www.kenyans.co.ke/).
It accepts only `/news/<numeric-id>-<slug>` stories, excluding `/news`, tracker,
featured, author, and other non-article routes. The inspected Drupal layout provides
JSON-LD title, author, and date metadata and stores prose in the news-body field.
Records use parser version `kenyans-archive-1.0`. August 2026 CDX inspection found
archived `/news/` stories, although Wayback coverage remains non-exhaustive.

```bash
python3 scripts/trial_scraper.py --source kenyans --limit 2
```

Discovery is a bounded sample of configured listings/feeds, not a complete archive.
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
