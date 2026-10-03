# Automated L0 and L1 annotations

Collection and annotation are decoupled. `annotations/service.py` exposes
`run_annotation_pipeline(layers, limit, article_ids, collection_run_id,
only_pending, trigger_type, config)`. The CLI and Flask trigger call this same
service. Existing collectors/parsers do not execute annotations. No worker, queue,
model fine-tuning, or human correction workflow is introduced.

## Database setup

Apply the additive migration once, after existing ingestion migrations:

```bash
psql "$DIRECT_DATABASE_URL" -f migrations/20261003_add_automated_annotations.sql
```

The migration was applied to the configured development Supabase database during
implementation. Other deployments must apply it separately; do not rerun the SQL
blindly because table creation is intentionally not silently idempotent.

`annotation_runs` records lifecycle, trigger, requested layers, collection-run
filter, counters, method versions, exact selected article-version IDs, configuration,
summaries and secret-safe failure types. Counters count **article versions**, while
per-layer summaries count **new decisions**. `processed = success + failed + skipped`.
A version is successful if at least one requested result was persisted and no
requested evaluation failed; blocked L1 does not make an otherwise successful L0
an infrastructure failure. Run status is `completed`, `completed_with_errors`,
`failed`, or `interrupted` following processing. Execution is serialized with a
PostgreSQL advisory lock across CLI/UI triggers.
The dedicated lock connection uses autocommit, avoiding a long idle transaction.
Backend-identity heartbeats run before each version and before each result write;
losing that connection stops the run rather than continuing without serialization.
Use a direct PostgreSQL connection or the Supabase **session pooler (5432)**;
the transaction pooler (6543) is rejected for session-level annotation locks.
A disconnected lock-release connection is invalidated and logged without masking
an already checkpointed completed run. Existing collector locking is unchanged.

`automated_annotations` is append-only through the service. Every result links to
its article, exact extraction version, annotation run, layer, method/version and
timestamp. L1 additionally links to the exact valid compatible L0 result that
authorized it. Records retain evidence, reason codes and nullable confidence.
Compatible existing outputs are read once for the selected cohort under the run
lock, rather than queried for each article. Newly forced L0 still invalidates any
cached L1 dependent on an older L0; label algorithms/method identities are unchanged.
Historical results are never updated by `--force`. RLS is enabled with no anonymous
browser grants; the configured backend PostgreSQL role needs appropriate access.

Future human validation and final/reference labels must use separate logical
records/tables; they must not overwrite these automated outputs.

## Running

Use the same private GCS/Supabase environment and ADC configuration as collection:

```bash
source .venv/bin/activate
python3 scripts/run_annotations.py --layer l0
python3 scripts/run_annotations.py --layer l1
python3 scripts/run_annotations.py --layer l0,l1 --limit 20
```

The service selects article versions in stable `created_at, id` order. `--limit`
caps selected versions, not successful outcomes. Without a limit it considers the
entire matching database corpus; confirm pilot membership before a full run.
Repeatable UUID filters narrow selection:

```bash
python3 scripts/run_annotations.py --layer l0,l1 --collection-run-id <uuid> --limit 20
python3 scripts/run_annotations.py --layer l0,l1 --article-id <uuid>
python3 scripts/run_annotations.py --layer l0,l1 --limit 20 --force
```

`--article-id` refers to the article's database UUID, not its canonical SHA-256 ID.
Default only-pending selection skips compatible existing results. L1-only execution
does **not** implicitly run L0; records lacking a current valid L0 are skipped.
With both layers requested, invalid/review L0 outputs block L1. A new forced L0
decision makes prior L1 results historical until L1 is run against that new gate.
Forced reprocessing appends rows; changed configuration produces a different method
identity automatically. `--minimum-body-chars` is an optional L0 override.
Exit `0` indicates no infrastructure/evaluation failures; exit `2` indicates failures.
Invalid/review/ambiguous automated labels are successful evaluations, not errors.

## L0: `extraction_quality_rules`, `l0-v1.0`

Pure deterministic checks validate title, body, source, canonical domain, publication
metadata, raw/processed `gs://` references, hash and parser version. The service reads
the persisted processed JSON once per evaluated version, pinned to its recorded GCS
generation when present, and compares source/canonical/hash/parser lineage with the
database. It only reads the configured processed bucket. Raw object existence is
not fetched per record; references are validated without additional raw GCS requests.
Missing processed objects yield persisted invalid L0 results; transient GCS/database
errors yield recorded per-version failures and do not abort following versions.
L1 refuses a missing or mismatched processed input even if a previous L0 was valid;
its fetched body must still match the immutable article-version hash. That is a
recorded failure rather than a semantic label derived from fallback metadata.

Defaults are centralized in `annotations/schemas.py`: minimum body **200 characters
and 35 words**; fewer than **60 characters** is unusable. These are initial engineering
thresholds requiring sampled validation, not empirically calibrated research criteria.

| Severity | Checks / example reasons | Label |
| --- | --- | --- |
| Hard | Missing title/body/source/URL/references/hash/parser; wrong domain; unusable body; invalid/mismatched hash; lineage mismatch; missing processed object; obvious block page | `invalid` |
| Soft | Short body; missing/invalid publication date; suspected boilerplate, paywall, truncation or HTML body; preserved non-reporting corporate trial | `needs_review` |
| None | Required quality and provenance checks pass | `valid` |

Calendar-valid date-only/timezone-naive publication strings are accepted without
inventing a timezone. Missing/invalid dates are explicitly recorded with reasons.
Stored source date precision/timezone still requires later research validation.
Confidence is **NULL** for L0. Evidence contains lengths, thresholds and severity
reason codes, never full article content. Invalid records are retained, not deleted.

## L1: `kenya_relevance_hybrid`, `l1-v1.0`

The curated, versioned `annotations/resources/kenya_v1.json` includes all 47 counties,
name variants, selected towns/cities, Kenya/Kenyan/Swahili demonyms, institutions,
administrative terminology and a bounded foreign-place list. County names were
checked against the [State Department for Devolution list](https://www.devolution.go.ke/county-information/).
Other aliases, institution ambiguity flags and foreign entries are engineering
resources requiring domain review; the gazetteer is neither exhaustive nor a NER model.

Evidence comes **only from title and article text**, using normalized Unicode,
case-insensitive word-boundary matching. Publisher identity supplies no score.
Evidence records matched county/place/institution/foreign lists, ambiguity flags,
country mention count, gazetteer version and scores. It does not record sensitive
text excerpts, victim names or exact-address spans.

Weights/thresholds are centralized: explicit country mention **3** (capped at three);
distinct unambiguous places **3** (capped at three); unambiguous institutions **3**
(capped at two); generic administrative terms **0.5** (capped at two, only supplementing
existing strong support); foreign places **3** (capped at three). Kenya and foreign
decision thresholds are **3**. Ambiguous names such as Busia/Meru/Nandi/Kikuyu/Eastleigh
and acronyms such as DCI/ODPP require stronger corroborating evidence and cannot
decide alone. Overlapping county/town aliases are deduplicated before scoring.

* `kenya`: Kenya support at or above threshold with no foreign-place evidence.
* `not_kenya`: foreign support at or above threshold, no strong Kenya support, and
  no ambiguous Kenya-like place/institution evidence.
* `ambiguous`: mixed, weak, conflicting, or absent geographic evidence.

For Kenya/foreign labels, confidence is `support / (support + 2)`; ambiguous confidence
is `2 / (abs(kenya_score - foreign_score) + 2)`. This is deterministic normalized
**label/evidence support, not a calibrated probability**. An ambiguity score of 1
may mean equally balanced or absent evidence; it does not mean an article is relevant.
Both thresholds and confidence behavior must be assessed using a small stratified
reference sample before substantive research use. Mixed articles are deliberately
held as ambiguous even if one side scores higher. This initial scorer does not
resolve reported-event location and cannot establish validated Kenya eligibility yet.

## Monitor and protected trigger

Existing collection pages remain available. New pages:

* `/annotations`: current default-method counts, L0 pending, L1 pending among valid L0.
* `/annotations/runs` and `/annotations/runs/<uuid>`: lifecycle, counts, methods,
  result breakdown, errors and summaries.
* `/annotations/l0` and `/annotations/l1`: source/label-filtered current results.
* `/articles/<uuid>`: historical automated results and extraction-version lineage.

Current queries resolve the latest default-method result per version/layer; L1 is
current only if it depends on the current valid L0. Custom parameter versions remain
visible in run detail and article history. Historical result views are explicitly
separate from current counts. Full article content is not displayed.

`POST /annotations/run` is **disabled by default**. To enable it locally, set the
following in your ignored `.env` with two distinct random secrets of at least 32
characters:

```text
ANNOTATION_UI_ENABLED=1
ANNOTATION_UI_TOKEN=<random execution secret>
FLASK_SECRET_KEY=<different random session-signing secret>
```

Restart the app. The form requires the execution secret and a signed-session
CSRF token; secrets are not stored in roadmap files or printed by application logs.
Only L0, L1 or both are allowed, and synchronous UI batches are capped at **20**
versions. The form token rotates after validation to prevent accidental browser
resubmission with the updated session. Execution over plain HTTP is permitted only for
loopback clients; remote requests require HTTPS. App Engine cookies are Secure;
session cookies are HttpOnly and SameSite Strict. Keep secrets out of tracked
deployment files and configure trusted HTTPS handling before enabling remote UI
execution. This capability gate is not a full user/reviewer authentication system.

The observed 20-version real trial took about 140 seconds. The installed Gunicorn
default worker timeout is 30 seconds, so use a longer timeout when enabling local
synchronous execution:

```bash
gunicorn --timeout 600 -b 127.0.0.1:8080 main:app
```

`app.yaml` keeps its existing read-only deployment defaults. Leave remote UI
execution disabled until hosting request/worker deadlines and trusted HTTPS
handling are explicitly configured. Use the CLI for full-corpus runs.

## Research logs and validation

Structured events cover run/layer start, completion, skip, failure, IDs, methods,
labels, duration and safe error types. Logs contain no full article text, secrets or
database connection strings. Counters/errors are checkpointed after each version.

Tests use synthetic records, mocked GCS/HTTP, fake repositories and executed
SQLite window queries for current-result semantics. Actual bounded-run observations belong in
`docs/roadmap/IMPLEMENTATION_STATUS.md`; do not put identifying article data there.
Automated outputs are **not gold labels**. The next milestone is stratified and
uncertainty-focused human validation, threshold/calibration/error analysis, and
versioned reference labels before advancing to L2 under the roadmap's gates.
