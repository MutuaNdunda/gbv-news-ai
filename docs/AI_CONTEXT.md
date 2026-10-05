# GBV News AI — AI Project Context

> This file is a fast technical orientation for AI coding agents. Read AGENTS.md for development/research constraints and README.md for operational commands. The source code remains authoritative for actual implementation.

## 1. Project Summary

GBV News AI is a postgraduate research project for an ethical, human-supervised,
near-real-time multilingual system that will identify, classify, geotag, and map
gender-based violence (GBV) reporting in Kenyan digital news. The repository is in
the **Automated Annotation Pipeline — L0/L1 validation** roadmap milestone, with
user-authorized L2 engineering work implemented after the collection MVP.
Current State records 536 versions; 407 was an older planning snapshot.
Supabase still contained 536 article versions on 5 October 2026. Neither count
establishes a validated final corpus. Broad
news sources are Daily Nation, Citizen Digital, The Standard, The Star Kenya, Tuko,
Kenyans.co.ke, and Taifa Leo. Automated L0/L1 engines are implemented, with human
validation and research exit-gate evidence still pending.

Implemented technologies are Python, Requests, Beautiful Soup, lxml, Google Cloud
Storage, Supabase PostgreSQL, SQLAlchemy/psycopg, the Internet Archive CDX API/Wayback
replay service, Flask/Jinja, Gunicorn, and `unittest`. The implemented Flask UI is a
collection and annotation monitor with optional protected bounded execution and
a local, token-protected Human Review workspace.
L2 now has separate provisional weak supervision, private bootstrap exports,
AfroXLMR-compatible PyTorch training, installed-artifact inference and protected local review.
No research-trained L2 model, full L2 inference or independent L2 validation has been completed.
Read-only verification at 12:44 EAT on 5 October found L0 valid 519/review 17,
L1 v2 kenya 324/not_kenya 35/ambiguous 160, and L2 weak coverage 324/324:
gbv 7/not_gbv 15/borderline 302. The primary method is `l2-model-unconfigured`,
so the primary-model dashboard has zero predictions and 324 pending versions.
One current L1 review is recorded; no completed validation sample or L2 review
coverage is established. Latest recorded tests: 249 run, 248 passed, one optional
model integration test skipped. These are dated observations, not fixed corpus sizes.
NER, geocoding, completed sampled human validation, mapping,
and remote reviewer authentication remain future research work. Before roadmap-related
implementation, run `python3 scripts/sync_roadmap.py` and read all four snapshots
plus `docs/roadmap/IMPLEMENTATION_STATUS.md`. The public Sheet controls planning;
the existing architecture remains the technical baseline.

```text
Publisher archive/listing
        -> source-specific discovery and scraper
        -> conservative HTTP/Wayback retrieval
        -> raw response persisted to GCS
        -> shared normalization + source-specific parsing
        -> normalized object in GCS + lineage in Supabase
        -> shared annotation runner: L0 -> persist -> valid L0 -> L1 -> persist
        -> current L1 Kenya -> L2 weak label or configured-model prediction -> persist
        -> Flask collection/annotation monitor
        -> protected local review UI + separate append-only human_validations
        -> sampled human validation (workflow available; sample not completed)
        -> research model validation, NER/geocoding and analytical map (future)
```

## 2. Current Repository Tree

Generated caches, virtual environments, Git internals, and collected files under
`data/` are omitted.

```text
gbv-news-ai/
├── AGENTS.md
├── README.md
├── requirements.txt
├── requirements-l2.txt          # optional PyTorch/Transformers training/inference
├── .env.example
├── .gitignore
├── app/                         # Flask factory, routes, services, templates, static
├── annotations/                 # L0/L1 rules, L2 weak/model pipeline, review contracts
├── database/
│   ├── models.py                # existing Supabase schema mappings
│   ├── session.py               # environment and SQLAlchemy engine/session setup
│   └── repositories/
│       ├── articles.py          # article/version upsert, deduplication, counts
│       ├── annotations.py       # append-only outputs, current queries, run lifecycle
│       ├── human_validations.py # separate reviews, revisions, status/cohort queries
│       ├── collection_runs.py   # run lifecycle and advisory locking
│       └── collection_run_scans.py # idempotent per-source/month progress
├── docs/
│   ├── AI_CONTEXT.md
│   ├── app_engine_deployment.md
│   ├── collection_protocol.md
│   ├── annotations.md           # rule/specification, schema and operator guide
│   └── roadmap/                 # public planning snapshots/config + engineering log
├── migrations/
│   ├── 20260909_add_collection_run_scans.sql
│   ├── 20260910_expand_collection_sources.sql
│   ├── 20261003_add_taifaleo_source.sql
│   ├── 20261003_add_automated_annotations.sql
│   ├── 20261004_add_human_validations.sql
│   ├── 20261005_add_l2_annotations.sql
│   └── 20261005_add_l2_human_validations.sql
├── models/
│   ├── classification/          # empty placeholder
│   └── ner/                     # empty placeholder
├── notebooks/
│   └── experiments.ipynb        # empty placeholder file
├── scrapers/
│   ├── archive.py
│   ├── common.py
│   ├── citizen.py
│   ├── kenyans.py
│   ├── nation.py
│   ├── standard.py
│   ├── star.py
│   ├── tuko.py
│   ├── taifaleo.py
│   └── wayback.py
├── scripts/
│   ├── collect_monthly.py
│   ├── test_infrastructure_connections.py
│   ├── trial_scraper.py
│   ├── import_local_trials.py
│   ├── run_annotations.py
│   ├── build_kenya_gazetteer.py
│   ├── compare_l1_versions.py
│   ├── prepare_l2_training_data.py
│   ├── train_l2_classifier.py
│   ├── smoke_l2.py
│   └── sync_roadmap.py
├── main.py                      # App Engine/Gunicorn Flask entrypoint
├── app.yaml                     # App Engine Python 3.14 configuration
├── storage/
│   ├── gcs.py                   # ADC-backed GCS adapter
│   ├── logging.py               # GCS run log handler
│   └── persistence.py           # object/database write coordinator
└── tests/
    ├── fixtures/
    │   ├── citizen_archive_article.html
    │   ├── kenyans_archive_article.html
    │   ├── nation_archive_article.html
    │   ├── standard_archive_article.html
    │   ├── star_archive_article.html
    │   ├── tuko_archive_article.html
    │   └── trial_article.html
    ├── test_citizen_archive.py
    ├── test_kenyans_archive.py
    ├── test_collection_run_scans.py
    ├── test_monitor.py
    ├── test_monitor_services.py
    ├── test_monthly_collection.py
    ├── test_nation_archive.py
    ├── test_persistence.py
    ├── test_standard_archive.py
    ├── test_star_archive.py
    ├── test_tuko_archive.py
    ├── test_trial_scraper.py
    ├── test_human_review.py
    ├── test_l2_human_review.py
    ├── test_l2_model.py
    ├── test_l2_pipeline.py
    ├── test_l2_queries.py
    ├── test_l2_training.py
    ├── test_l2_ui.py
    ├── test_l2_weak_supervision.py
    └── storage_fakes.py
```

The initial Supabase article/run schema is mapped by the repository. Versioned SQL
migrations add `collection_run_scans` and expand article/scan source constraints for
Tuko, Kenyans.co.ke, and Taifa Leo. Apply migrations in filename order to each database.

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
dependency. Optional ML packages (PyTorch, Transformers, SentencePiece and
SafeTensors) are declared separately in `requirements-l2.txt`; the monitor and
rule-based layers do not require that stack.

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
Optional annotation UI execution uses `ANNOTATION_UI_ENABLED=1`,
`ANNOTATION_UI_TOKEN` and `FLASK_SECRET_KEY`; distinct random secrets of at least
32 characters are required. Mutation is disabled by default.

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

**Called by:** All six publisher modules.

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

### `scrapers/tuko.py`

**Purpose:** Tuko archive discovery and parsing from the configured August 2026
homepage seed and compatible Wayback captures.

**Key components:** Numeric-ID story validation beneath one to three section path
components, canonical restoration, promotional/related/ad/figure cleanup from
`.post__content`, ISO publication metadata normalization, archive provenance, and
parser version `tuko-archive-1.0`.

### `scrapers/kenyans.py`

**Purpose:** Kenyans.co.ke archive discovery and parsing from the configured July
2024 homepage seed and compatible Wayback captures.

**Key components:** Strict `/news/<numeric-id>-<slug>` validation, canonical
restoration, JSON-LD metadata, Drupal news-body extraction, ISO publication metadata
normalization, archive provenance, and parser version `kenyans-archive-1.0`. August
2026 CDX results include compatible news captures, with non-exhaustive coverage.

### `scripts/trial_scraper.py`

**Purpose:** Executable bounded, single-snapshot trial collector.

**Key components:**

- `SOURCES` registers the six publisher modules.
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

**Purpose:** Offline `unittest` regression coverage. The seven HTML fixtures are small,
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
- `test_tuko_archive.py`: numeric-ID URL rules, discovery, metadata/body/date parsing,
  cleanup, canonical restoration, provenance, and rejection paths.
- `test_kenyans_archive.py`: news URL rules, Drupal-body and metadata parsing,
  canonical restoration, provenance, and rejection paths.
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

**Status: L2 INFRASTRUCTURE IMPLEMENTED; RESEARCH MODEL PENDING.** `classification/`
and `ner/` remain empty placeholders. L2 dataset preparation, task-specific training,
manifest/checksum handling and offline inference live under `annotations/` and
`scripts/`. Generated artifacts belong in ignored `models/artifacts/` or private
`data/l2/`. Tiny synthetic checkpoints demonstrate code execution, not a trained
research GBV classifier. NER and independent model evaluation remain pending.

### `app/`, `main.py`, and `app.yaml`

**Status: COLLECTION/ANNOTATION MONITOR AND LOCAL REVIEW IMPLEMENTED.** `create_app` wires shared
database/storage-backed services into blueprints for `/`, `/runs`, `/articles`, and
`/health`. Jinja/Bootstrap pages show grouped corpus metrics, paginated runs/articles,
scan progress, filters/search, and article-version provenance without article text.
Annotation routes provide L0/L1/L2 machine results, separate weak/model views and
protected local Human Review. Verified text is available only in unlocked local
sessions; confirmed/corrected decisions append separate history.
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
| `source` | Required internal key: `nation`, `citizen`, `standard`, `star`, `tuko`, or `kenyans`. |
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

### 5.1 Layered Annotation Schema

Annotation is not a single classification task. Automated L0/L1/L2 infrastructure and planned later
layers support distinct, traceable tasks that match the research goals and keep extraction
quality, relevance decisions, semantic labels, locations, and privacy review separate.

| Layer | Task | Label type | Example labels/output |
|---|---|---|---|
| **L0 – Extraction Quality** | Is the parsed article valid? | Three-way gate + reasons | `valid`, `needs_review`, `invalid` |
| **L1 – Kenya Relevance** | Is the article about Kenya? | Categorical decision + evidence | `kenya`, `not_kenya`, `ambiguous` |
| **L2 – GBV Relevance** | Is the article about GBV? | Categorical decision + confidence | `gbv`, `not_gbv`, `borderline` |
| **L3 – GBV Type** | What kind of GBV is reported? | Multi-label | `physical`, `sexual`, `emotional`, `economic`, `harmful_practice`, `online` |
| **L4 – Location** | Where did the incident happen? | Text spans + NER labels + normalized geocode | `["Nairobi", "Kibera"]` mapped to the appropriate county/ward |
| **L5 – Privacy Risk** | Does the article contain personally identifiable or sensitive information? | Multi-label | `victim_name`, `exact_address`, `photo`, `none` |

The collection-era `articles.kenya_relevance` field remains `needs_review`;
automated L1 decisions live separately in `automated_annotations`. Publisher origin
supplies no relevance score. `annotation_runs` stores lifecycle, trigger, counters,
method versions, configuration, selected-version IDs, summaries and safe errors.
`automated_annotations` stores append-only layer/label/confidence/evidence/reasons
with article, article-version, run, method/version and timestamp lineage. L1 links
to the exact current valid compatible L0; L2 links to the exact current compatible
L1 Kenya result. `human_validations` stores separate exact-result review revisions.
Final/adjudicated reference-label datasets remain future work and must not overwrite
automated outputs.

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
- Supabase `annotation_runs` and `automated_annotations` for versioned automated outputs.
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

The architecture uses sequential collection and annotation pipelines with a Flask
monitor. Publisher modules own discovery/parsing rules; shared scraper
modules own safe retrieval and normalization; scripts orchestrate dedicated GCS and
database layers. Classification is not a scraper responsibility. Structured lineage
stays outside publisher parsing. Flask services reuse those layers and issue grouped
queries without listing GCS for counts. L2 weak/model infrastructure and local review
are implemented; NER/geocoding, the analytical map and remote review remain future work.
`annotations/service.py` is the shared L0/L1/L2 orchestrator
for CLI, bounded UI and future automation. It uses an advisory lock, stable selection,
generation-pinned processed GCS reads, per-version persistence/checkpoints, secret-safe
logs, continuation after individual failures, and pending-only method-aware selection.
Annotation locking uses a dedicated autocommit direct/session-pooler connection with
backend-identity checks before writes; a lost lease stops further processing.
Transaction-pooler connections are rejected. Disconnected cleanup does not mask
completed checkpoints. Collection locking remains unchanged.
Current compatible prerequisite/results are fetched once per locked cohort, avoiding
per-article lookup queries while preserving forced-L0/L1 dependency checks.
L1 refuses missing/mismatched processed input or a body hash inconsistent with the
version accepted by L0; fallback metadata alone cannot produce a semantic label.
`--force` appends history; current queries resolve compatible L0/L1/L2 dependencies.

L0 uses deterministic hard/soft extraction and provenance rules, minimum 200
characters/35 words (under 60 characters is unusable), labels valid/review/invalid,
and NULL confidence (`extraction_quality_rules`, `l0-v1.0`). L1 uses a versioned
offline-built `kenya-gazetteer-v2.0` with 47 counties, 307 sub-counties,
290 constituencies, 1,448 wards, 916 localities, 1,827 areas and 36 retained towns.
Pinned upstream files, licenses, checksums and reference discrepancies live under
`annotations/resources/upstream/`; `scripts/build_kenya_gazetteer.py --check`
reproduces the resource. Cached token-trie matching supplies one lexical place
signal per canonical name, with parent metadata and explicit ambiguity flags.
Weights and country/institution/foreign logic remain unchanged. Current identity is
`kenya_relevance_hybrid`, `l1-v2.0-<resource-sha256-prefix>`; custom weights append
another digest. Historical `l1-v1.0` remains executable using
`AnnotationConfig(l1_gazetteer="v1")` / CLI `--l1-gazetteer v1` and its results
remain untouched. The subsequent user-authorized forced full v2 run on 4 October appended 519
fresh decisions: Kenya 324, not Kenya 35 and ambiguous 160, with 17 gated skips
and zero failures. Current v2 eligible pending count is zero. All 519 v1 rows
and 20 earlier v2 trial rows were preserved. V1 coverage does not satisfy v2
pending queries. This is deterministic lexical
relevance, not NER, geocoding, L4 or a calibrated classifier. See `docs/annotations.md`.

Flask routes include `/annotations`, `/annotations/runs`, `/annotations/runs/<uuid>`,
`/annotations/l0`, `/annotations/l1`, `/annotations/l2` and protected
GET/POST `/annotations/review/<uuid>`. `/annotations/l2/<uuid>` redirects to shared
review. `mode=weak` selects bootstrap results; default L2 counts refer to model
predictions. Protected `POST /annotations/run` still executes only L0/L1.
Article detail includes annotation history. The opt-in trigger shares the same
runner, requires execution-token and rotating signed-session CSRF validation,
caps batches at 20, and requires HTTPS for remote clients. No queue or reviewer
authentication system is introduced.

## 12. Machine Learning State

### Implemented

- Provisional versioned L2 weak supervision, private binary development-data export,
  task-specific PyTorch/Transformers training CLI and checksummed local-artifact inference.
- Separate weak/model method identities, exact upstream gates, uncalibrated binary
  probabilities/thresholds, append-only outputs and synthetic architecture smoke.
- Protected local review for L0/L1/L2; human decisions remain separate from machines.

### Partially implemented

- Multilingual source fields can be preserved, but language detection/evaluation does
  not exist and observed metadata may be empty.

### Planned

- Reviewed GBV inclusion/exclusion specification, independent human validation and calibration.
- Research baseline and AfroXLMR/XLM-R training/evaluation with an approved corpus.
- English, Swahili, Sheng, and code-switched evaluation for accuracy, fairness,
  robustness, and latency.
- Separate location NER, incident-location reasoning, normalization, and geocoding.
- Final corpus freeze, duplicate-aware held-out splits and evaluation/reference datasets.
- Remote authenticated reviewer workflows and integrated location correction.

The primary trained model is currently unconfigured. Tiny synthetic local checkpoints
and successful pipeline tests do not establish research accuracy or calibration.
Pretrained AfroXLMR must not be described as an existing GBV classifier.

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

Automated annotation (after applying the additive annotation migration):

```bash
python3 scripts/run_annotations.py --layer l0,l1 --limit 20
python3 scripts/run_annotations.py --layer l0
python3 scripts/run_annotations.py --layer l1
gunicorn -b 127.0.0.1:8080 main:app
```

Use UUID membership filters before wider pilot execution. Inspect `/annotations`
and the stored run summary. L1-only never silently runs L0; invalid/review L0 blocks L1.

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

For implementation sequencing and readiness, the public Google Sheet is the
planning source of truth. Sync first, then use Roadmap, Current State, Stage Gates
and Annotation Layers alongside the repository engineering log. Report mismatches;
planning prose does not justify destructive changes or establish code completion.

For actual technical behavior, use this priority:

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

- Source-specific archive URL validation, discovery, and parsing for seven publishers.
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
- Public anonymous roadmap sync with validated/atomic CSV snapshots, read-only
  `--check`, and public identifier overrides; no Google authentication.
- Local JSON/JSONL trial import with matching raw evidence and cloud deduplication.
- Automated extraction-quality and Kenya-relevance layers, additive schema,
  append-only version lineage, shared CLI/UI runner, protected bounded execution,
  run/results monitoring and structured safe logs.
- Versioned L1 v2 gazetteer with historical v1 execution preserved; complete current
  L2 weak coverage and separate training/inference infrastructure.
- Protected local L0/L1/L2 Human Review, direct unlock, exact lineage, append-only
  decisions/history, method-separated review counts and filtered navigation.
- Offline tests cover parsing, orchestration, persistence/recovery, monitor behavior,
  local imports, roadmap sync, rules, generation reads, actual SQL current queries,
  gating, counters, failure isolation, force/idempotency and UI protection. See
  IMPLEMENTATION_STATUS.md for current executed test count and real-run observations.
- Git exclusion of collected data.

### Partially Implemented

- Archive coverage and historical-layout compatibility vary by source/capture.
- Language is preserved from metadata but not detected or validated.
- Publication timestamp parsing is source-specific and sometimes timezone-unknown.
- Automated L0/L1 decisions exist, but extraction quality and Kenya relevance have
  not passed sampled human validation or calibration. Protected local review tooling
  exists; sample validation remains pending.
- Near-real-time is an objective, but only retrospective/snapshot collection exists.

### Planned / Not Implemented

- Independent reference-label datasets, stratified sampling, completed validation/calibration.
- Research-trained/configured GBV classifier, full primary-model inference, agreed
  accuracy/fairness metrics and corpus freeze/held-out evaluation.
- NER, location-role reasoning, geocoding, maps, and privacy-aware presentation.
- Remote authenticated reviewer, administrative, map and public-user workflows.
- Prospective continuous or near-real-time scheduling and latency measurement.

## 17. Known Limitations / Technical Debt

- Wayback indexes captures, not the full publisher output; missing/late/inaccessible
  captures create non-random omissions.
- Publisher parsers are tied to inspected historical layouts and synthetic fixtures do
  not prove compatibility with every archive page.
- Missing or unparseable publication dates exclude records from monthly storage/counts;
  some valid dates have unknown timezone.
- Language and automated Kenya relevance require sampled validation.
- Raw HTML may be incomplete, restricted, malformed, or unavailable; these attempts
  are logged and skipped.
- Scan tracking, source expansion and automated annotations have versioned SQL
  migrations; the initial Supabase ingestion tables predate repository migration
  history. The local Human Review UI has additive migrations. Inspection on 5 October
  found the expected L2 annotation checks/index/trigger absent, although the L2
  human-review extension is installed; apply `20261005_add_l2_annotations.sql` before
  further automated L2 writes. No prospective scheduler or end-to-end latency instrumentation exists.
- Tests cover important deterministic behavior but do not perform live archive
  compatibility checks or broad extraction-quality evaluation.
- The zero-byte notebook remains a placeholder; database models are implemented and
  map the existing Supabase ingestion schema.

## 18. Immediate Next Steps

Pull the roadmap first; do not use this orientation file as a competing task list.
The inspected roadmap currently prioritizes:

1. Reconcile the roadmap's 407-record planning count with the 536 observed versions.
2. Inspect L0 flags and resolve parser defects through versioned reprocessing.
3. Review initial annotation specification, thresholds and gazetteer with domain experts.
4. Inspect L1 uncertainty and subgroup coverage; all 519 L0-valid versions now
   have L1 decisions following the authorized full run.
5. Create a small stratified/uncertainty-focused human reference sample and metrics.
6. Inspect L2 weak uncertainty, verify schema prerequisites and agree the GBV codebook.
7. Satisfy documented gates before research L2 training/evaluation, L3–L5 or corpus freeze.

See `docs/roadmap/IMPLEMENTATION_STATUS.md` for current L0/L1/L2 implementation
status, required decisions and actual validation evidence. The real 20-version
trial completed with L0 valid 20 and L1 Kenya 14 / non-Kenya 3 / ambiguous 3,
zero failures. L0 subsequently covered all 536 versions: valid 519, needs_review 17,
invalid 0, with no processing failures. Missing dates (12) and short bodies (5)
require inspection. The initial full-run CLI had a post-completion lock-release
error; annotation-specific autocommit/heartbeat/cleanup handling now addresses it.
That historical milestone passed 155 tests; the latest recorded suite ran 249
(248 passed, one optional integration test skipped). Automated execution does not
establish human-validated reference labels.
Full L1 completed with 499 new decisions and 17 gated skips, no failures and exit 0.
Across 519 eligible versions, historical v1 totals were Kenya 307 / non-Kenya 73 / ambiguous
139; both L0 and eligible v1 L1 pending were zero at that verification.
The new default v2 has a separate compatible identity. Its authorized forced
full run completed on 4 October with 519 current decisions and zero eligible
pending, while preserving v1 history. The pending-only combined repeat
selected zero records and added no duplicate decisions. The 1,055-row total
(536 L0 + 519 L1) describes the v1 milestone, not the current historical-row total.
The latest compatible v2/weak counts are recorded at the top of this document;
history is retained. See IMPLEMENTATION_STATUS.md for run lineage.

GCS and Supabase are the accepted implemented persistence providers. Do not introduce
another object store or database provider without a new architecture decision.

## 19. AI Task Routing Guide

| Task | Read first |
|---|---|
| Roadmap-driven implementation | Run `scripts/sync_roadmap.py`; read all four `docs/roadmap/*.csv` snapshots, `IMPLEMENTATION_STATUS.md`, `AGENTS.md`, and this file |
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

## Protected local Human Review — 4 October 2026

All machine count cards open paginated label-filtered result lists. Rows and article
history entries open GET/POST `/annotations/review/<uuid:annotation_id>`. Only an
unlocked local session fetches the exact processed extraction using the existing
GCS reader and recorded object generation; lineage/body hashes are checked. Private
text/notes are escaped and review responses use private/no-store caching.

`human_validations` links the exact automated annotation, article and extraction
version, copies the machine label/support, and appends configured reviewer identity,
guideline version, controlled decision/label, reason/category, notes and timestamp.
Revisions supersede a prior review without updating it or any machine row. Latest
review status uses timestamp/UUID order; row locks, unique chain indexes and stale
form checks prevent competing revisions. New machine rows require new reviews.

Human Review is default-disabled, CSRF protected and restricted to direct localhost
requests. It requires a review token and Flask secret of at least 32 characters,
a configured actual reviewer identity and actual guideline version. Session access
expires after 30 minutes. No remote multi-user authentication exists. See README
and `docs/annotations.md` for configuration. Counts reflect current v2 (160 ambiguous),
while historical v1 results remain individually inspectable/reviewable. No automatic
review, sampling, calibration, downstream layers or research-validation completion
is introduced by this workflow.

L2 local Human Review was added on 5 October 2026. New databases must apply
`migrations/20261005_add_l2_human_validations.sql` after existing human-validation
and L2 annotation migrations. L2 labels are gbv/not_gbv/borderline. Direct L2
results open the same unlock/review workflow, with exact L1 prerequisite and
weak/model evidence. Dashboard review counts separate weak bootstrap from model
predictions; current compatibility and exact machine UUIDs prevent review inheritance.
Historical reviews remain accessible. No human decisions or validation metrics are
generated by adding this interface, and research gates remain open.
The extension is installed in development. The earlier L2 annotation migration's
expected checks/index/trigger were absent at the latest read-only inspection;
schema file presence and saved weak labels do not establish deployment readiness.
