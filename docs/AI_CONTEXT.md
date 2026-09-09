# GBV News AI — AI Project Context

> This file is a fast technical orientation for AI coding agents. Read AGENTS.md for development/research constraints and README.md for operational commands. The source code remains authoritative for actual implementation.

## 1. Project Summary

GBV News AI is a postgraduate research project for an ethical, human-supervised,
near-real-time multilingual system that will identify, classify, geotag, and map
gender-based violence (GBV) reporting in Kenyan digital news. The repository is in
the **data-collection MVP** phase. Its current objective is reliable, reproducible
collection and manual validation of broad news samples from Daily Nation, Citizen
Digital, The Standard, and The Star Kenya.

Implemented technologies are Python, Requests, Beautiful Soup, lxml, Google Cloud
Storage, Supabase PostgreSQL, SQLAlchemy/psycopg, the Internet Archive CDX API/Wayback
replay service, Flask/Jinja, Gunicorn, and `unittest`. The implemented Flask UI is a
read-only collection monitor. AfroXLMR/PyTorch, NER, geocoding, annotation, mapping,
and public/reviewer workflows remain future research work.

```text
Publisher archive/listing
        -> source-specific discovery and scraper
        -> conservative HTTP/Wayback retrieval
        -> raw response persisted to GCS
        -> shared normalization + source-specific parsing
        -> normalized object in GCS + lineage in Supabase
        -> read-only Flask collection monitor
        -> manual quality/relevance review (current manual responsibility)
        -> ML/NER/geocoding/review/map workflows (future)
```

## 2. Current Repository Tree

Generated caches, virtual environments, Git internals, and collected files under
`data/` are omitted.

```text
gbv-news-ai/
├── AGENTS.md
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── app/                         # Flask factory, routes, services, templates, static
├── database/
│   ├── models.py                # existing Supabase schema mappings
│   ├── session.py               # environment and SQLAlchemy engine/session setup
│   └── repositories/
│       ├── articles.py          # article/version upsert, deduplication, counts
│       ├── collection_runs.py   # run lifecycle and advisory locking
│       └── collection_run_scans.py # idempotent per-source/month progress
├── docs/
│   ├── AI_CONTEXT.md
│   ├── app_engine_deployment.md
│   └── collection_protocol.md
├── migrations/
│   └── 20260909_add_collection_run_scans.sql
├── models/
│   ├── classification/          # empty placeholder
│   └── ner/                     # empty placeholder
├── notebooks/
│   └── experiments.ipynb        # empty placeholder file
├── scrapers/
│   ├── archive.py
│   ├── common.py
│   ├── citizen.py
│   ├── nation.py
│   ├── standard.py
│   └── star.py
├── scripts/
│   ├── collect_monthly.py
│   ├── test_infrastructure_connections.py
│   └── trial_scraper.py
├── main.py                      # App Engine/Gunicorn Flask entrypoint
├── app.yaml                     # App Engine Python 3.14 configuration
├── storage/
│   ├── gcs.py                   # ADC-backed GCS adapter
│   ├── logging.py               # GCS run log handler
│   └── persistence.py           # object/database write coordinator
└── tests/
    ├── fixtures/
    │   ├── citizen_archive_article.html
    │   ├── nation_archive_article.html
    │   ├── standard_archive_article.html
    │   ├── star_archive_article.html
    │   └── trial_article.html
    ├── test_citizen_archive.py
    ├── test_collection_run_scans.py
    ├── test_monitor.py
    ├── test_monitor_services.py
    ├── test_monthly_collection.py
    ├── test_nation_archive.py
    ├── test_persistence.py
    ├── test_standard_archive.py
    ├── test_star_archive.py
    ├── test_trial_scraper.py
    └── storage_fakes.py
```

The initial Supabase article/run schema is mapped by the repository. A versioned SQL
migration adds `collection_run_scans`; it has been applied to the configured database.

## 3. Root Files

### `AGENTS.md`

**Purpose:** Authoritative research objectives, ethics, architecture direction, data
handling rules, coding standards, and current priorities.

**Read/edit when:** Read before substantial work. Edit only when project-wide rules,
research constraints, or accepted architecture priorities change.

### `README.md`

**Purpose:** Project introduction and the operational guide for environment setup,
tests, bounded trials, monthly collection, monitoring, resume, outputs, and Git safety.

**Read/edit when:** Read before running collection. Keep commands synchronized with
the actual CLIs whenever script options or output locations change.

### `requirements.txt`

**Purpose:** Declares scraper dependencies plus SQLAlchemy, psycopg, python-dotenv,
the Google Cloud Storage client, Flask, and Gunicorn.

**Read/edit when:** Edit only when executable code gains or removes a justified
dependency. There are currently no pandas, PyTorch, Transformers, or ML framework
packages.

### `.gitignore`

**Purpose:** Excludes environments, caches, secrets, model artifacts, local databases,
logs, and all collected content beneath `data/`. Only `README.md` and `.gitkeep` files
inside `data/` may be tracked.

**Read/edit when:** Update when a new generated or sensitive artifact type is added.
Never force-add collected research data.

### Environment configuration

`.env.example` lists the Supabase fields, GCS bucket names, GCP project, and optional
crawler user agent. Real values live only in ignored `.env`. Local GCS access uses ADC;
service-account JSON keys must not be stored in the repository.

## 4. Directory and File Map

### `scrapers/common.py`

**Purpose:** Shared URL safety, HTTP behavior, discovery, metadata extraction,
normalization, hashing, and baseline article construction.

**Key components:**

- `normalize_url(url)` accepts HTTP(S), lowercases the network location, removes URL
  fragments, and rejects missing hosts or embedded credentials.
- `allowed_url(url, hosts)` restricts hosts and ports to the supplied allowlist and
  standard HTTP(S) ports.
- `Client` uses a Requests session, checks and caches `robots.txt`, observes configured
  or robots crawl delays, performs up to three attempts for network/transient server
  failures, limits redirects, and validates every redirect target.
- `discover(html, base_url, accepts)` finds, filters, normalizes, and deduplicates links.
- `parse_article(...)` parses JSON-LD or publisher body selectors, rejects active
  paywalls/foreign canonicals, removes common non-article elements, and creates the
  shared normalized record.
- `PARSER_VERSION = "1.0"` is the baseline parser version; publisher modules override
  it in their final records.

**Inputs:** HTML bytes/text, URLs, allowed hosts, body selectors, request settings.

**Outputs:** Requests responses, discovered URLs, or normalized article dictionaries.

**Called by:** Every publisher module and both collection scripts.

**Dependencies:** Requests, Beautiful Soup, Python URL/robots/hash/time libraries.

**Edit this when:** Changing cross-publisher access, normalization, shared parsing, or
base schema behavior.

**Do not put here:** Publisher layouts, URL patterns, capture constants, GBV decisions,
database persistence, or ML inference.

### `scrapers/archive.py`

**Purpose:** Shared validation and link discovery for Wayback replay URLs.

**Key components:** `archive_parts(url, publisher_hosts)` validates a 14-digit replay
timestamp and embedded publisher URL. `discover_archive(...)` converts live/relative
links to replay links, rejects premium-labelled links, and deduplicates originals.

**Inputs/outputs:** Archived listing HTML and replay URLs in; validated
`(timestamp, original_url)` pairs or archive article URLs out.

**Called by:** All four publisher modules.

**Edit this when:** Archive replay syntax or shared archive discovery changes.

**Do not put here:** Publisher-specific URL/body rules or monthly CDX orchestration.

### `scrapers/nation.py`

**Purpose:** Daily Nation archive discovery and parsing from the configured June 2024
homepage snapshot.

**Key components:** Source/host/capture/listing/body constants; `archive_parts`,
`is_article`, `accepts`, `accepts_fetch`, `discover`, and `parse`. It accepts selected
Nation reporting sections, rebuilds article paragraphs from Nation wrappers, rejects
premium/active-paywall content, restores canonical publisher URLs, and assigns parser
version `nation-archive-2.0` plus archive provenance.

**Inputs:** Nation Wayback listing/article HTML and replay URLs.

**Outputs:** Replay candidates and normalized Daily Nation article dictionaries.

**Called by:** `scripts/trial_scraper.py` and `scripts/collect_monthly.py`.

**Dependencies:** `scrapers.common`, `scrapers.archive`, Beautiful Soup.

**Edit this when:** Nation URL rules, layouts, selectors, or source metadata change.

**Do not put here:** Other publishers, collection scheduling, storage, or GBV labels.

### `scrapers/citizen.py`

**Purpose:** Citizen Digital archive discovery and parsing from the configured March
2026 homepage snapshot and compatible archive captures.

**Key components:** The standard publisher interface plus Citizen section/ID URL
patterns. `parse` restores canonical URLs, decodes HTML-escaped JSON-LD, normalizes a
nested author-name shape, parses ISO publication timestamps, marks missing timezone
information, and assigns `citizen-archive-1.1`.

**Inputs/outputs/called by/dependencies:** Same boundary as `nation.py`, for Citizen
archive pages; depends on shared modules, Beautiful Soup, JSON, HTML unescaping, and
datetime parsing.

**Edit this when:** Citizen URL patterns, metadata encoding, layouts, or dates change.

**Do not put here:** General client policy, orchestration, classification, or storage.

### `scrapers/standard.py`

**Purpose:** The Standard archive discovery/parsing, including bounded listing
expansion from the configured August 2020 snapshot.

**Key components:** Standard article/listing validators; `expanded_candidates` performs
breadth-first listing retrieval, prioritizes domestic sections, then round-robins
article candidates across pages. `parse` handles prose stored as direct text nodes,
removes related/caption/control material, parses explicit EAT timestamps as UTC+03:00,
and assigns `standard-archive-1.1`.

**Inputs:** Standard replay listings/articles and `max_pages`.

**Outputs:** Candidate triples `(url, discovery_url, method)` and normalized records.

**Called by:** Both collection scripts through the publisher interface.

**Dependencies:** Shared scraper modules, Beautiful Soup, datetime, collections,
itertools, and URL parsing.

**Edit this when:** Standard layouts, sections, pagination, URL rules, or dates change.

**Do not put here:** Global crawl limits, persistence, or relevance decisions.

### `scrapers/star.py`

**Purpose:** The Star Kenya archive discovery and parsing from the configured December
2025 homepage snapshot and compatible captures.

**Key components:** Dated article URL validation across configured sections, premium
rejection, body parsing, visible-date fallback, unknown-timezone marking, and parser
version `star-archive-1.0`.

**Inputs/outputs/called by/dependencies:** Same publisher boundary as `nation.py`, for
Star replay pages; depends on shared scraper modules, Beautiful Soup, and datetime.

**Edit this when:** Star URL patterns, layouts, sections, or date displays change.

**Do not put here:** Cross-source orchestration, databases, or ML logic.

### `scripts/trial_scraper.py`

**Purpose:** Executable bounded, single-snapshot trial collector.

**Key components:**

- `SOURCES` registers the four publisher modules.
- Supabase repositories provide existing URLs and `(source, content_hash)` identities.
- `candidates` uses source-specific expanded discovery when available, otherwise feeds
  then listings.
- Raw responses are persisted to GCS before parsing; normalized results are then
  persisted/indexed through `CollectionPersistence`.
- `run_trial_extraction` orchestrates sources sequentially and caps retrieval attempts
  at five times the requested save limit.
- `main` exposes repeatable `--source`, `--limit` (default 20 per source), `--max-pages`
  (Standard listings, default 1), `--delay`, and a durable `--run-name`.

**Inputs:** CLI settings, publisher listings/pages, Supabase identities, and GCS state.

**Outputs:** Raw/processed GCS objects, Supabase run/article/version lineage, and GCS
progress, trial-count, and log artifacts. Reruns skip indexed duplicates.

If processed storage succeeds but database indexing fails, the run checkpoint stores
only non-secret object references. Resume loads the existing processed object and
retries Supabase indexing before discovery, without refetching the article.

**Called by:** Users directly; monthly collection imports its source registry and
service factory.

**Dependencies:** Publisher modules, shared client, Beautiful Soup, storage/database layers.

**Edit this when:** Bounded trial orchestration, CLI options, deduplication indexing,
or article persistence coordination changes.

**Do not put here:** Publisher selectors, monthly CDX scanning, GBV classification.

### `scripts/collect_monthly.py`

**Purpose:** Executable retrospective archive collector and publication-month reporter.

**Key components:**

- `months_descending` validates and orders the requested window newest-first.
- `publication_month` derives the stated publication calendar month; it never uses
  archive/scrape time as a substitute.
- `index_url` and `parse_index` build/validate paginated Wayback CDX queries.
- Database aggregation counts records globally and optionally by collection run.
- `report` replaces progress and monthly CSV objects in the runs bucket.
- `run` scans each capture month/source, filters source article URLs, fetches/parses,
  filters to the requested publication window, deduplicates, persists, and checkpoints.
- `main` validates CLI values, applies a PostgreSQL advisory lock, and configures
  console/GCS logging.

CLI options are `--start-month`, `--end-month`, repeatable `--source`, `--delay`,
`--max-index-pages`, `--max-fetches-per-month`, and `--run-name`. Zero limits mean no
cap. Defaults are January–August 2026, all sources, and a two-second delay.

**Inputs:** Wayback CDX index/replays, requested month window, source and safety limits,
Supabase identities, and GCS-cached CDX pages.

**Outputs:** Raw/processed GCS objects and Supabase lineage plus GCS `progress.json`,
`monthly_counts.csv`, `collection.log`, and hashed CDX cache objects under the run prefix.

**Called by:** Users directly.

**Dependencies:** `scrapers.common.Client`, publisher modules and persistence helpers
from `scripts/trial_scraper.py`, plus the database and storage layers.

**Edit this when:** Monthly/CDX orchestration, checkpointing, status semantics,
publication-window logic, or reporting changes.

**Do not put here:** Publisher HTML rules, annotation logic, model inference, or UI.

### `tests/`

**Purpose:** Offline `unittest` regression coverage. The five HTML fixtures are small,
synthetic representations of inspected layouts, not collected research data.

- `test_trial_scraper.py`: shared metadata/body parsing, URL safety, paywall/canonical
  rejection, robots behavior, redirects, stable IDs and cloud-persistence orchestration.
- `test_nation_archive.py`: Nation provenance, discovery, content cleanup, premium/
  paywall rejection, and redirect restrictions.
- `test_citizen_archive.py`: escaped JSON-LD, nested author, body layouts, discovery,
  date uncertainty, and rejection paths.
- `test_standard_archive.py`: direct-text extraction, EAT normalization, bounded
  listings, round-robin candidates, pagination, and rejection paths.
- `test_star_archive.py`: metadata/body/date extraction, discovery, paywalls, canonical
  and redirect restrictions.
- `test_monthly_collection.py`: month attribution, CDX continuation, GCS-backed
  resume/idempotence, and index-failure pausing through offline fakes.
- `test_persistence.py`: raw-first ordering, GCS/database failures, retry behavior,
  and idempotent extraction resolution.

Run all tests with `python3 -m unittest discover -s tests -v`. Add a focused
fixture and regression whenever parser, URL, normalization, deduplication, or monthly
state behavior changes. Live publisher access is not part of the test suite.

### `data/`

**Purpose:** Legacy/local paths are not used as durable collector output. GCS is the
authoritative object store and Supabase is the structured index.

Do not enumerate, expose, commit, or push collected files. Everything under `data/`
is ignored except intentional `README.md` and `.gitkeep` files.

### `docs/collection_protocol.md`

**Purpose:** Methodological and operational contract for the January–August 2026
archive collection: scope, sampling, commands, outputs, statuses, and coverage limits.

**Edit this when:** The retrospective collection methodology or report semantics
change. Keep it consistent with code and README commands.

### `database/` and `storage/`

**Status: IMPLEMENTED FOR COLLECTION.** SQLAlchemy models map `collection_runs`,
`articles`, and `article_versions`; repositories resolve runs, query deduplication and
counts, upsert logical articles, and idempotently resolve extraction versions. The GCS
adapter uses ADC, immutable create-only raw/processed writes, object generations, and
run-artifact reads/writes. `CollectionPersistence` enforces raw-before-parse/index
ordering without putting provider details in publisher modules.

### `models/`

**Status: PLANNED / NOT YET IMPLEMENTED.** `classification/` and `ner/` are empty.
There is no tokenizer, dataset loader, model code, checkpoint, training, inference,
evaluation, or model registry.

### `app/`, `main.py`, and `app.yaml`

**Status: IMPLEMENTED FOR READ-ONLY COLLECTION MONITORING.** `create_app` wires shared
database/storage-backed services into blueprints for `/`, `/runs`, `/articles`, and
`/health`. Jinja/Bootstrap pages show grouped corpus metrics, paginated runs/articles,
scan progress, filters/search, and article-version provenance without article text.
The health route performs database/table and bucket-metadata reads only. App Engine
uses Python 3.14 and Gunicorn; deployment secrets are documented separately.

### `notebooks/experiments.ipynb`

**Status: PLANNED / NOT YET IMPLEMENTED.** This is currently a zero-byte placeholder,
not a valid populated notebook and not part of executable architecture.

## 5. Current Data Model

`scrapers.common.parse_article` produces the base dictionary. A valid record requires
a title, nonempty article body, and canonical URL on the expected publisher host.
Publisher parsers and collection scripts then add provenance and run fields.

| Field | Current behavior |
|---|---|
| `source` | Required internal key: `nation`, `citizen`, `standard`, or `star`. |
| `url` | Normalized original publisher URL passed into shared parsing, not replay URL. |
| `canonical_url` | Required normalized publisher canonical; used for identity/deduplication. |
| `title` | Required headline from JSON-LD, Open Graph, or `h1`. |
| `author` | String; empty when unavailable. Lists/dictionaries are flattened. |
| `published_at` | Publication metadata as a string or missing/falsey; publisher parsers normalize supported formats. |
| `article_text` | Required extracted body with paragraphs separated by blank lines. |
| `language` | JSON-LD/HTML language value or empty string; no detector exists. |
| `scraped_at` | UTC ISO 8601 timestamp created during parsing. |
| `content_hash` | SHA-256 hex digest of the exact normalized `article_text`. |
| `parser_version` | Source parser version after publisher parsing. |
| `section` | JSON-LD article section or empty string. |
| `kenya_relevance` | Always starts as `needs_review`. |
| `kenya_relevance_basis` | Human-readable reminder that publisher origin does not prove relevance. |
| `publisher_name` / `publisher_domain` | Added by archive publisher parsers. |
| `content_scope` | Currently `news_reporting` for successfully parsed publisher records. |
| `archive_url` | Actual normalized Wayback replay URL, added by publisher parser. |
| `archive_capture_timestamp` | Fourteen-digit capture timestamp from replay URL. |
| `published_at_raw` | Optional original date string added by Citizen/Standard/Star date handling. |
| `publication_timezone` | Optional `unknown` when a parsed date lacks timezone information. |
| `publication_date_needs_review` | Optional flag for missing/unparseable publication dates. |
| `requested_url` | URL requested by the collection script; a replay URL in current archive flows. |
| `discovery_url` / `discovery_method` | Listing or CDX query provenance and discovery method. |
| `http_status` | Successful article response status. |
| `article_id` | SHA-256 of `"<source>:<canonical_url>"`; stable parent prefix for content-addressed raw/JSON objects. |
| `raw_object_uri` / `raw_object_generation` | Added after raw-first GCS persistence and stored with version lineage. |
| `publication_month` | Monthly collector only; derived from `published_at`. |
| `collection_run` | Monthly collector run name; durable linkage uses `collection_run_id`. |
| `discovery_capture_month` | Monthly collector only; month whose CDX captures were scanned. |

JSON is UTF-8 and pretty-printed. Timestamps use ISO 8601 where parsing succeeds;
timezone-naive source dates remain timezone-naive and are explicitly marked unknown.
The monthly collector does not save records without a usable publication date.

## 6. Data Collection Flow

```text
CLI
 ├─ trial_scraper.main -> run_trial_extraction
 └─ collect_monthly.main -> lock/config -> run
             |
             v
publisher discovery (listing or monthly CDX)
             |
             v
common.Client: URL allowlist -> robots -> throttle/retry -> redirect validation
             |
             v
raw HTML -> GCS raw bucket (create-only)
             |
             v
publisher.parse -> date/window/hash checks -> normalized JSON in processed GCS
             |
             v
Supabase article upsert + idempotent article_version/run linkage
             |
             v
GCS run progress/counts/log/CDX-cache artifacts
```

Trial discovery starts at configured archived snapshots. Monthly discovery queries
successful HTML captures from Wayback CDX for each publisher domain/capture month,
then lets publication metadata determine the record's actual corpus month.

## 7. Storage Architecture

### Current storage — IMPLEMENTED

- Private raw, processed, and run-artifact GCS buckets authenticated through ADC.
- Create-only raw and processed writes with GCS URI/generation capture.
- Supabase `collection_runs`, logical `articles`, and extraction `article_versions`.
- Supabase `collection_run_scans` for queryable source/capture-month counters/status.
- GCS-backed progress, CSV reports, collection logs, and CDX caches.
- PostgreSQL advisory locks for same-run concurrency safety.
- Pending-index checkpoints that recover a processed-object/database failure without
  refetching the source response.

Collectors do not use local paths as durable storage or resume state.

## 8. Deduplication and Identity

- `normalize_url` removes fragments and normalizes the network location, while keeping
  path/query; publisher canonical validation prevents cross-domain identities.
- `article_id` is deterministic SHA-256 over `source:canonical_url`.
- `content_hash` is deterministic SHA-256 over `article_text`.
- Supabase queries index canonical, requested, and archive URLs plus source/content hashes.
- Collection skips an existing URL or an existing `(source, content_hash)` pair.
  Therefore identical text is deduplicated within a publisher but remains traceable
  if published by different sources.
- Content hashes distinguish immutable raw and processed objects beneath each logical
  article prefix. GCS create preconditions prevent replacement, and the database unique
  constraints resolve repeated logical articles and identical parser/content versions.

The relevant implementation is in `scrapers/common.py`, `storage/persistence.py`,
`database/repositories/articles.py`, and the two collection scripts.

## 9. Collection Run and Resume Logic

Monthly runs use `gs://<GCS_RUNS_BUCKET>/runs/<run-name>/`. `progress.json` records
exact configuration, month order, counters, statuses, and timestamps. Resume requires
an exact configuration match. A PostgreSQL advisory lock prevents concurrent use.

`monthly_counts.csv` contains source, publication month, new articles for this run,
total Supabase-indexed articles, same-month capture scan status, and the review-needed
relevance marker. `collection.log` records retrieval and monthly summaries. Hashed
`.cdx.json` files cache exact CDX query responses; continuation keys paginate results.

Important scan statuses are `pending`, `running`, `index_exhausted`,
`index_exhausted_with_gaps`, `fetch_limit`, `index_page_limit`, and `index_failed`.
Run-level statuses include `running`, `interrupted`, `paused_index_unavailable`,
`finished_with_gaps`, `index_scans_finished`, `completed`, and `failed`. Three
consecutive index failures pause the run with remaining scans pending. Bounded limits
intentionally produce gap statuses. Ctrl-C checkpoints an interrupted monthly run.
The same command and run name resume it.

## 10. External Systems

- **Publisher websites — PARTIALLY IMPLEMENTED:** Publisher domains and layouts are
  validated, but current configured single-snapshot flows retrieve archived replays.
- **Internet Archive CDX and Wayback Machine — IMPLEMENTED:** Used for archive index
  discovery and page replay. Coverage depends on what the archive captured and serves.
- **Google Cloud Storage — IMPLEMENTED:** Durable raw, processed, and run artifacts.
- **Supabase PostgreSQL — IMPLEMENTED:** Collection runs, logical articles, versions,
  per-scan progress, deduplication, counts, and lineage through SQLAlchemy/psycopg.

## 11. Application Architecture

The architecture remains a sequential collection pipeline plus a read-only Flask
monitor, not a microservice topology. Publisher modules own discovery/parsing rules; shared scraper
modules own safe retrieval and normalization; scripts orchestrate dedicated GCS and
database layers. Classification is not a scraper responsibility. Structured lineage
stays outside publisher parsing. Flask services reuse those layers and issue grouped
queries without listing GCS for counts. ML/NER/geocoding and review interfaces remain
downstream future stages.

## 12. Machine Learning State

### Implemented

- No machine-learning functionality is implemented.

### Partially implemented

- Multilingual source fields can be preserved, but language detection/evaluation does
  not exist and observed metadata may be empty.

### Planned

- Annotation and weak-supervision workflows with independent human validation.
- Baseline and AfroXLMR task-specific GBV classification.
- English, Swahili, Sheng, and code-switched evaluation for accuracy, fairness,
  robustness, and latency.
- Separate location NER, incident-location reasoning, normalization, and geocoding.
- Versioned datasets, preprocessing, tokenizers, models, thresholds, and predictions.
- Human confirmation/correction that preserves original predictions.

No training, inference, checkpoint, metric, dataset loader, or experiment result is
present. Pretrained AfroXLMR must not be described as an existing GBV classifier.

## 13. Research and Ethics Constraints

- Collect broad GBV and non-GBV reporting; never construct the corpus solely through
  known GBV keywords.
- Protect victim privacy and minimize personally identifying or exact-location data,
  especially in public views.
- Preserve URLs, timestamps, raw/processed lineage, parser versions, and later model/
  dataset versions for reproducibility.
- Treat weak labels as non-ground-truth and preserve model predictions separately from
  human corrections.
- Do not bypass authentication, paywalls, CAPTCHAs, robots restrictions, or publisher
  access controls; use conservative request rates.
- Keep collected research data private in GCS/Supabase and out of Git.

## 14. How to Run the Project

From the repository root:

```bash
python3 -m pip install -r requirements.txt
gcloud auth application-default login
python3 scripts/test_infrastructure_connections.py
python3 -m unittest discover -s tests -v
```

Small single-snapshot trial:

```bash
python3 scripts/trial_scraper.py \
  --source citizen --limit 2 \
  --run-name trial-citizen-smoke
```

Bounded monthly smoke test:

```bash
python3 scripts/collect_monthly.py \
  --start-month 2026-08 --end-month 2026-08 \
  --source citizen \
  --max-index-pages 1 --max-fetches-per-month 2 \
  --run-name citizen-aug-smoke
```

Full January–August 2026 retrospective run:

```bash
python3 scripts/collect_monthly.py \
  --start-month 2026-01 --end-month 2026-08 \
  --run-name jan-aug-2026
```

Monitor the selected run:

```bash
gcloud storage cat gs://gbv-news-ai-runs/runs/jan-aug-2026/progress.json
```

Resume by rerunning the exact monthly command with its original run name and
configuration. Do not run two processes against the same run. See README.md and
`docs/collection_protocol.md` before operating a full run.

## 15. Source of Truth

Use this priority:

1. Current executable source code.
2. Database migrations/schema, when present.
3. AGENTS.md for research/development constraints.
4. README.md for operational behavior.
5. `docs/AI_CONTEXT.md` for orientation.
6. Project logs/history.

When this document conflicts with the current code, inspect the code and update
AI_CONTEXT.md.

## 16. Current Implementation Status

### Implemented

- Source-specific archive URL validation, discovery, and parsing for four publishers.
- Shared URL normalization, host/port restrictions, robots checks, throttling, retries,
  redirect validation, metadata/body extraction, and content hashing.
- Bounded single-snapshot trials and retrospective monthly CDX collection.
- Publication-month filtering, GCS raw/processed/run persistence, Supabase lineage,
  deterministic identity, deduplication, progress/report/log/cache objects, advisory
  locking, and exact-configuration resume.
- Recovery of pending database indexing directly from processed GCS objects.
- An infrastructure connection checker for Supabase tables and GCS permissions.
- A read-only Flask/Jinja collection monitor with dashboard, run, article, and health
  views. It uses grouped/paginated database queries and bucket metadata checks.
- 44 offline tests covering parser behavior, orchestration, persistence failures,
  retry, idempotency, scan persistence, monitor routes, and monitor query shape.
- Git exclusion of collected data.

### Partially Implemented

- Archive coverage and historical-layout compatibility vary by source/capture.
- Language is preserved from metadata but not detected or validated.
- Publication timestamp parsing is source-specific and sometimes timezone-unknown.
- Kenya relevance is flagged for manual review but no review workflow exists.
- Manual extraction-quality review is required; no review tooling exists.
- Near-real-time is an objective, but only retrospective/snapshot collection exists.

### Planned / Not Implemented

- Annotation, weak-labeling, and human-review persistence.
- GBV classification, AfroXLMR fine-tuning, datasets, evaluation, inference, and model
  lineage.
- NER, location-role reasoning, geocoding, maps, and privacy-aware presentation.
- Administrative, annotation, reviewer, map, and public-user workflows.
- Prospective continuous or near-real-time scheduling and latency measurement.

## 17. Known Limitations / Technical Debt

- Wayback indexes captures, not the full publisher output; missing/late/inaccessible
  captures create non-random omissions.
- Publisher parsers are tied to inspected historical layouts and synthetic fixtures do
  not prove compatibility with every archive page.
- Missing or unparseable publication dates exclude records from monthly storage/counts;
  some valid dates have unknown timezone.
- Language and Kenya relevance require manual verification.
- Raw HTML may be incomplete, restricted, malformed, or unavailable; these attempts
  are logged and skipped.
- Only `collection_run_scans` currently has a checked-in migration; the initial
  Supabase tables predate repository migration history. There is no annotation UI, ML layer,
  prospective scheduler, or end-to-end latency instrumentation.
- Tests cover important deterministic behavior but do not perform live archive
  compatibility checks or broad extraction-quality evaluation.
- The zero-byte notebook remains a placeholder; database models are implemented and
  map the existing Supabase ingestion schema.

## 18. Immediate Next Steps

Aligned with the current data-collection MVP:

1. Run and manually audit bounded samples for each publisher against raw HTML.
2. Record extraction-quality results and add regression fixtures for observed failures.
3. Complete/resume the January–August monthly scans and document per-source archive
   gaps without claiming exhaustive coverage.
4. Add a repeatable validation/report script for missing fields, body length, dates,
   language metadata, and Kenya-relevance review queues.
5. Define versioned promotion criteria from trial data to a reviewed research corpus.
6. Manually validate GCS/Supabase trial outputs and their lineage joins.
7. Add versioned migrations matching the existing Supabase ingestion schema.
8. Exercise failure recovery and operational monitoring on bounded live trials.
9. Design the human annotation/review data model before introducing weak labels or ML.
10. Begin baseline/model work only after collection quality and reviewed dataset
    procedures are reproducible.

GCS and Supabase are the accepted implemented persistence providers. Do not introduce
another object store or database provider without a new architecture decision.

## 19. AI Task Routing Guide

| Task | Read first |
|---|---|
| Scraper/parser | `AGENTS.md`, `README.md`, `scrapers/common.py`, `scrapers/archive.py`, relevant publisher module, collection scripts, relevant tests/fixture |
| Monthly collection | `README.md`, `docs/collection_protocol.md`, `scripts/collect_monthly.py`, `scripts/trial_scraper.py`, `tests/test_monthly_collection.py` |
| Storage | `AGENTS.md`, this file, `storage/gcs.py`, and `storage/persistence.py` |
| Database | `AGENTS.md`, this file, `database/models.py`, session setup, and repositories |
| ML/NER | `AGENTS.md`, this file, normalized article schema; `models/` is currently empty |
| Flask collection monitor | `AGENTS.md`, this file, `app/routes/`, `app/services/`, monitor tests, and deployment guide |
| Tests | Relevant implementation, matching `tests/test_*.py`, and synthetic fixture; run the full offline suite |
| Documentation/operations | Current CLIs, `README.md`, `docs/collection_protocol.md`, and this file |

## 20. Maintenance Rule

Update this file whenever a major directory, module, database table, pipeline stage,
CLI command, external integration, or architectural responsibility changes.

Do not use this file as a chronological project log. It should describe the CURRENT
repository.
