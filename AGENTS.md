# AGENTS.md

## 1. Project Purpose

This repository supports a postgraduate research project focused on building an ethical, human-supervised, near-real-time multilingual AI system for identifying, classifying, geotagging, and mapping gender-based violence (GBV) reporting in Kenyan digital news.

The system will collect news articles from selected Kenyan media sources, process and classify them using multilingual transformer models such as AfroXLMR, extract relevant geographic locations, geocode those locations, and present the resulting information through a web-based dashboard and map.

This is both a research project and a working software system. Changes should therefore prioritize reproducibility, traceability, methodological soundness, data protection, and maintainability.

---

## 2. Core Research Objectives

The implementation should support the following objectives:

1. Collect digital news articles from selected Kenyan news publishers.
2. Build a multilingual corpus containing English, Swahili, Sheng, and code-switched content where available.
3. Develop and evaluate transformer-based GBV classification models.
4. Extract geographic entities from relevant articles.
5. Geocode extracted locations for mapping.
6. Support human review and correction of model outputs.
7. Evaluate model accuracy, fairness, robustness, and latency.
8. Support near-real-time ingestion, inference, and visualization.
9. Maintain clear lineage between source articles, annotations, model versions, and predictions.

---

## 3. Initial News Sources

Initial collection targets include:

* Daily Nation
* Citizen Digital
* The Standard
* The Star Kenya
* Tuko
* Kenyans.co.ke
* Taifa Leo

Additional sources may be added later.

Each source should have its own scraper implementation rather than placing all publisher-specific logic inside one file.

---

## 4. Project Structure

The high-level repository structure includes implemented collection components and
placeholders for later research stages:

```text
.
├── app/
│   └── Flask web application and dashboard
│
├── scrapers/
│   ├── nation.py
│   ├── citizen.py
│   ├── kenyans.py
│   ├── standard.py
│   ├── star.py
│   ├── tuko.py
│   ├── taifaleo.py
│   ├── common.py
│   ├── archive.py
│   └── wayback.py
│
├── data/
│   ├── trials/
│   │   ├── raw/
│   │   │   ├── nation/
│   │   │   ├── citizen/
│   │   │   ├── kenyans/
│   │   │   ├── standard/
│   │   │   ├── star/
│   │   │   ├── tuko/
│   │   │   └── taifaleo/
│   │   └── processed/
│   │
│   ├── raw/
│   └── processed/
│
├── models/
│   ├── classification/
│   └── ner/
│
├── database/
│   ├── models.py
│   ├── session.py
│   └── repositories/
│
├── storage/                   # GCS persistence and run logging
├── migrations/                # Versioned PostgreSQL schema changes
│
├── notebooks/
│   └── experiments.ipynb
│
├── tests/
│   └── fixtures/
│
├── scripts/
├── docs/
│
├── requirements.txt
├── main.py                    # Flask/Gunicorn entrypoint
├── app.yaml                   # App Engine configuration
├── .env
├── .gitignore
├── AGENTS.md
└── README.md
```

Agents may extend this structure when justified, but should avoid unnecessary complexity during the early research and MVP stages.

---

## 5. Trial Data Collection

Trial outputs remain unvalidated research candidates regardless of storage backend.
The cloud collectors `scripts/trial_scraper.py` and `scripts/collect_monthly.py`
persist raw HTML, normalized records, and run artifacts in private Google Cloud
Storage (GCS), with article/version/run metadata indexed in Supabase PostgreSQL.
They do not write collection output under `data/`.

The standalone exploratory collector `scrapers/wayback.py` uses repository-anchored
local output under:

```text
data/trials/
```

`scripts/import_local_trials.py` can explicitly migrate existing local JSON/JSONL trials
and raw snapshots into private GCS/Supabase. Its offline `--dry-run` validates input;
uploads reuse cloud deduplication and immutable object writes. Keep local originals,
use a consistent run configuration for retries, and do not treat upload as research
quality approval. See the README for default and legacy input-root commands.

Raw trial content should be stored under:

```text
data/trials/raw/
```

Source-specific trial data should use directories such as:

```text
data/trials/raw/nation/
data/trials/raw/citizen/
data/trials/raw/kenyans/
data/trials/raw/standard/
data/trials/raw/star/
data/trials/raw/tuko/
data/trials/raw/taifaleo/
```

Cleaned or normalized trial data should be stored under:

```text
data/trials/processed/
```

Trial data must not automatically be treated as final research data.

Do not move experimental datasets into the primary research dataset until their extraction and cleaning quality has been reviewed.

The repository `README.md` is the operator guide for trial collection. It documents
environment setup, offline validation, bounded single-snapshot trials, monthly smoke
tests, full retrospective collection, output inspection, monitoring, and resume/error
handling. Keep that guide aligned whenever collector commands, options, paths, or scan
statuses change.

All collected data is private research material and must not be committed or pushed
to Git, whether stored locally or in GCS/Supabase. Local trial output remains local;
cloud persistence does not authorize public sharing. The
repository `.gitignore` excludes everything under `data/` except `README.md`
documentation and `.gitkeep` placeholders. This covers raw HTML, normalized records,
run logs, counts, progress state, cached discovery responses, annotation exports, and
future collection-output directories. Never use `git add -f` to add these artifacts.
Small synthetic regression fixtures belong under `tests/fixtures/` and may be tracked.

---

## 6. Data Collection Principles

News collection should be conservative, reproducible, and respectful of publisher infrastructure.

Agents implementing scraping should:

* Prefer RSS feeds, XML sitemaps, structured metadata, and article listing pages where available.
* Use source-specific parsers.
* Avoid excessive request frequency.
* Use sensible delays, timeouts, and retries.
* Respect technical access restrictions.
* Do not bypass authentication, paywalls, CAPTCHAs, or other access controls.
* Avoid unnecessary collection of personal information.
* Preserve article provenance.
* Record the original article URL.
* Record the publisher.
* Record when the article was collected.
* Preserve publication timestamps where available.
* Prefer canonical URLs.
* Deduplicate articles before insertion into permanent storage.

Do not make the scraper responsible for deciding whether an article contains GBV.

The scraper should primarily collect news content. Classification should happen later.

---

## 7. Avoid Dataset Selection Bias

Do not collect only articles containing known GBV keywords.

The research corpus should contain both relevant and non-relevant articles.

For example, the collection process may include broad sections such as:

```text
News
Counties
Crime
Health
Education
Politics
Society
Courts
```

The classification pipeline should determine whether an article is related to GBV.

Keyword and rule-based filtering may be used for candidate discovery or weak supervision, but should not be the sole mechanism used to construct the dataset.

---

## 8. Standard Article Representation

Where practical, every scraper should produce a normalized article object with fields similar to:

```python
{
    "source": "",
    "url": "",
    "canonical_url": "",
    "title": "",
    "author": "",
    "published_at": "",
    "article_text": "",
    "language": "",
    "scraped_at": ""
}
```

Additional useful fields may include:

```python
{
    "section": "",
    "content_hash": "",
    "parser_version": "",
    "discovery_method": "",
    "http_status": ""
}
```

Do not create significantly different article schemas for different publishers unless unavoidable.

---

## 9. Raw Data Preservation

Where ethically and legally appropriate, preserve enough raw source material to reproduce parsing results.

Raw source snapshots may be stored separately from normalized article records.

The purpose is to allow:

* parser debugging,
* data-quality validation,
* reproducibility,
* reprocessing when extraction logic changes.

Do not expose or republish copyrighted source content unnecessarily.

---

## 10. Scraper Design

Publisher-specific logic should remain separated.

Example:

```text
scrapers/
├── nation.py
├── citizen.py
├── kenyans.py
├── standard.py
├── star.py
└── tuko.py
```

Shared HTTP, metadata, normalization, and archive helpers already live in
`scrapers/common.py` and `scrapers/archive.py`. Reuse these modules rather than
introducing parallel implementations. The layout includes:

```text
scrapers/
├── common.py
├── archive.py
├── nation.py
├── citizen.py
├── kenyans.py
├── standard.py
├── star.py
├── tuko.py
└── taifaleo.py
```

Shared functionality may include:

* HTTP requests,
* retries,
* rate limiting,
* canonical URL normalization,
* content hashing,
* common metadata extraction,
* logging.

Do not prematurely introduce a complex scraping framework unless the existing implementation becomes difficult to maintain.

Start with simple Python tooling where practical.

---

## 11. Preferred Scraping Technologies

The initial preferred stack is:

```text
Python
requests
BeautifulSoup
lxml
```

Use browser automation such as Playwright only when a publisher genuinely requires JavaScript rendering or interaction that cannot reasonably be handled through normal HTTP requests.

Do not introduce Selenium or Playwright by default.

---

## 12. Data Deduplication

Every collected article should eventually have a stable identifier.

Canonical URLs should normally be unique.

Content hashing may also be used to identify duplicate or syndicated articles.

Example:

```python
import hashlib

content_hash = hashlib.sha256(
    article_text.encode("utf-8")
).hexdigest()
```

Deduplication logic should be deterministic and testable.

---

## 13. Database Direction

The preferred research database is PostgreSQL.

SQLAlchemy may be used as the application ORM.

The ingestion layer already uses Supabase PostgreSQL through SQLAlchemy/psycopg.
Existing mappings separate `articles`, `article_versions`, `collection_runs`, and
`collection_run_scans`; private GCS objects retain raw and normalized content.
Preserve these interfaces and extraction lineage. Apply versioned SQL migrations
in filename order; do not assume that checked-in migrations have been applied to
every database.

The database should eventually distinguish between:

* source articles,
* annotations,
* weak labels,
* model predictions,
* extracted locations,
* geocoded locations,
* human reviews,
* model versions.

Avoid placing every piece of information into a single `articles` table.

---

## 14. Model Development

The initial multilingual transformer family under investigation is AfroXLMR.

The intended model-development flow is:

```text
Pretrained AfroXLMR
        ↓
Research corpus
        ↓
Annotation / weak supervision
        ↓
Training dataset
        ↓
Fine-tuning
        ↓
Validation
        ↓
Independent testing
        ↓
Deployment
```

Do not assume the pretrained AfroXLMR model is already a GBV classifier.

GBV classification requires task-specific fine-tuning.

---

## 15. Weak Supervision

Rule-based methods may be used to help bootstrap dataset creation.

Rules may consider:

* GBV terminology,
* crime terminology,
* victim references,
* perpetrator references,
* relationship context,
* police or court context,
* location references,
* exclusion patterns.

However:

* rule-generated labels are not ground truth;
* rules must not replace human validation;
* ambiguous cases should be reviewable;
* clean validation and test datasets should preferably be manually annotated.

The model must not be evaluated solely against labels generated using the same rules used to create its training data.

---

## 16. Human-in-the-Loop Design

Human oversight is a core component of the project.

The system should eventually support reviewers who can:

* inspect article content,
* inspect model predictions,
* confirm predictions,
* reject predictions,
* correct classification categories,
* correct extracted locations,
* flag uncertain cases,
* add annotation notes.

Human corrections should be stored separately from original model outputs.

Do not silently overwrite model predictions with human decisions.

Both should remain traceable.

---

## 17. Model Traceability

Every model prediction should eventually be associated with:

```text
model_name
model_version
prediction_timestamp
predicted_class
confidence_score
preprocessing_version
```

Where applicable, also retain:

```text
training_dataset_version
tokenizer_version
decision_threshold
```

Never overwrite historical predictions simply because a newer model has been introduced.

---

## 18. Named Entity Recognition and Geotagging

Location extraction should remain separate from GBV classification.

The conceptual processing sequence is:

```text
Article
   ↓
GBV classification
   ↓
Location extraction / NER
   ↓
Location normalization
   ↓
Geocoding
   ↓
Map representation
```

Do not assume every location mentioned in an article represents the incident location.

Future implementation should distinguish, where possible, between:

* incident location,
* reporting location,
* police station,
* court location,
* victim residence,
* unrelated contextual locations.

---

## 19. Application Architecture

The implemented web interface uses Flask. It is a read-only collection monitor
with dashboard totals, run and source/month scan progress, searchable article
metadata, extraction lineage, and infrastructure health. It does not display full
article text or provide collection controls. This operational monitor is separate
from the planned GBV review and mapping interface.

The Flask application may eventually support:

* article browsing,
* model predictions,
* confidence scores,
* maps,
* human review,
* annotation workflows,
* administrative functionality.

The machine-learning inference layer may later be separated into its own service if deployment requirements justify it.

Avoid premature microservice architecture during early research development.

---

## 20. Near-Real-Time Processing

The system is intended to support near-real-time article processing.

Architecture decisions should therefore allow measurement of:

```text
article discovery latency
article retrieval latency
text preprocessing latency
model inference latency
NER latency
geocoding latency
end-to-end processing latency
```

Do not optimize prematurely.

First establish correct, reproducible processing before optimizing performance.

---

## 21. Testing

Important scraper and transformation logic should be testable without repeatedly calling live publisher websites.

Representative HTML samples may be stored under:

```text
tests/fixtures/
```

For example:

```text
tests/fixtures/nation_article.html
tests/fixtures/citizen_article.html
```

Tests should verify important fields such as:

* title,
* publication date,
* article body,
* canonical URL,
* source,
* deduplication behavior.

When fixing parser bugs, add or update regression tests where practical.

---

## 22. Logging

Important pipeline operations should produce useful logs.

Relevant events include:

```text
article discovered
article fetched
article skipped
duplicate detected
parsing failed
retry attempted
article stored
classification completed
geocoding failed
human review completed
```

Avoid excessive debug logging in production environments.

Never log credentials or sensitive secrets.

---

## 23. Coding Standards

Agents should:

* Prefer readable Python over clever implementations.
* Keep functions focused.
* Use descriptive names.
* Avoid unnecessary duplication.
* Add docstrings where logic is non-obvious.
* Handle network and parsing failures gracefully.
* Use type hints where they improve clarity.
* Preserve existing interfaces when possible.
* Avoid large unrelated refactors.
* Keep commits and changes focused.

Do not rewrite major parts of the repository merely to satisfy stylistic preferences.

---

## 24. Dependency Management

Before adding a new dependency:

1. Check whether the functionality already exists in the standard library or current dependencies.
2. Confirm the dependency has a clear project benefit.
3. Avoid introducing multiple libraries that solve the same problem.
4. Update `requirements.txt`.
5. Document important infrastructure dependencies.

Avoid unnecessary framework proliferation.

---

## 25. Preferred Technology Stack

Current preferred technologies include:

```text
Python
Flask
PostgreSQL
SQLAlchemy
pandas
requests
BeautifulSoup
lxml
PyTorch
Hugging Face Transformers
AfroXLMR
Docker
Git
GitHub
```

Potential technologies may be introduced later only when justified.

Do not introduce Kafka, Kubernetes, distributed queues, or other high-complexity infrastructure merely because they may be useful at scale.

The research MVP should remain simple.

---

## 26. Security

Never commit:

```text
passwords
database credentials
API keys
cloud credentials
access tokens
private keys
secret configuration values
```

Use environment variables and `.env` files for local configuration.

`.env` must remain excluded from Git.

Do not print secrets into logs.

---

## 27. Privacy and Research Ethics

This project deals with potentially sensitive reports of violence.

Agents must avoid unnecessary processing or exposure of identifiable victim information.

Implementation decisions should support:

* data minimization,
* privacy protection,
* responsible reporting,
* human oversight,
* model accountability,
* traceability,
* ethical review.

Do not design functionality that unnecessarily exposes names or identifying information of victims.

Sensitive fields should not automatically be displayed on public-facing maps or dashboards.

---

## 28. Reproducibility

Important research outputs should be reproducible.

Where practical, record:

```text
dataset version
model version
code commit
experiment parameters
random seed
training metrics
evaluation metrics
timestamp
```

Do not rely solely on undocumented notebook experiments.

Useful experiments should eventually be converted into repeatable scripts or clearly documented procedures.

---

## 29. Git Practices

Before making significant changes:

```bash
git status
```

Keep changes scoped to the task.

Do not commit generated or collected datasets, secrets, large model checkpoints, or
temporary files. Collected data under `data/` must remain local even when a task asks
for other project changes to be committed or pushed.

Before committing or pushing, verify that Git is not tracking collected data:

```bash
git status --short
git ls-files data
```

Any output from the second command must be limited to intentional `README.md` and
`.gitkeep` files. If a collected artifact is already tracked, remove it from Git's
index without deleting the local copy, then recheck the staged diff.

Before committing:

```bash
git diff
git status
```

Use meaningful commit messages.

Example:

```text
Add initial Nation article scraper
```

rather than:

```text
updates
```

---

## 30. Agent Behaviour

AI coding agents working in this repository should:

1. Read this file before making substantial changes.
2. Inspect existing implementation before creating replacement architecture.
3. Reuse established project conventions.
4. Do not invent requirements that are not supported by the repository or research design.
5. Do not delete data, migrations, or research artifacts without clear justification.
6. Prefer incremental changes.
7. Explain important architectural changes.
8. Add tests when changing critical parsing or processing logic.
9. Preserve research traceability.
10. Prioritize correctness and reproducibility over speed.

When uncertain about a research assumption, document the uncertainty rather than silently treating it as fact.

---

## 31. Current Development Priority

The current milestone is **Automated Annotation Pipeline — L0 and L1**. The public
Google Sheet and synchronized snapshots in `docs/roadmap/` govern sequencing and
stage gates (see Section 34). Current State identifies a 407-record trial corpus;
this is not a validated final research dataset or a live database-count assertion.
Supabase contained 536 article versions when checked on 3 October 2026. The user
authorized L0 over all 536 after a successful 20-version L0/L1 trial, then explicitly
authorized L1 on the remaining 499 L0-valid versions. All 519 eligible versions now
have L1 decisions; the 17 L0 review cases remain gated.

Collection, normalization, cloud persistence, and operational monitoring are now
implemented for seven publishers, and automated L0/L1 now share a versioned service
and monitor (see Section 33). The next priorities are:

```text
1. Inspect automated L0 flags and resolve extraction defects by versioned reprocessing.
2. Review annotation specification, gazetteer, thresholds and corpus membership.
3. Inspect L1 uncertainty and source/language coverage over the agreed eligible corpus.
4. Perform sampled human validation, uncertainty/error analysis and metrics/reporting.
5. Progress to L2–L5, corpus freeze and model work only as roadmap gates permit.
```

Do not build advanced model-serving or distributed infrastructure before reliable data collection has been demonstrated.

---

## 32. Definition of a Good Change

A good contribution to this repository should be:

* relevant to the research objectives,
* understandable,
* testable,
* reproducible,
* minimally complex,
* ethically appropriate,
* traceable,
* maintainable.

When several implementations are possible, prefer the simplest approach that satisfies the research requirement.

---

## 33. Implemented Progress (Reviewed 3 October 2026)

This summary reflects repository implementation and operator documentation. It does
not establish production deployment, completed collection, or validated research
results. Read `README.md` for commands and `docs/collection_protocol.md` for sampling
and coverage limits; source code remains authoritative for behavior.

### Collection and parsing

* Source-specific archive discovery and parsers exist for Daily Nation, Citizen
  Digital, The Standard, The Star Kenya, Tuko, Kenyans.co.ke, and Taifa Leo.
* Shared collection code supports conservative request pacing, robots checks,
  timeouts, limited retries, publisher/redirect validation, and paywall detection.
* `scripts/trial_scraper.py` supports bounded cloud-backed trials. Standard also
  supports bounded category/listing pagination.
* `scripts/collect_monthly.py` supports January–August 2026 retrospective collection,
  scanning August backwards to January without GBV keyword filtering. Publication
  metadata determines corpus inclusion and monthly counts; capture dates do not
  substitute for publication dates.
* Monthly runs support cached paginated CDX discovery, resume with matching
  configuration, advisory locking, explicit incomplete/failed scan states, and
  configurable index matching and replay modes. Pending or failed scans must never
  be interpreted as zero publisher output or complete coverage.
* `scrapers/wayback.py` provides a standalone local exploratory collector. Its
  Taifa Leo path uses the source-specific parser and supports a bounded all-date
  CDX trial; the six older paths retain an experimental generic parser.
* Taifa Leo parsing supports inspected legacy and WordPress layouts. A legacy
  `en-US` template language is flagged for review rather than accepted as the
  article language. Swahili-source support does not establish validated multilingual
  corpus coverage.

### Persistence and traceability

* Raw snapshots are persisted before parsing; normalized JSON and run artifacts
  are stored in private GCS. Create-only object writes prevent silent replacement.
* Supabase indexes logical articles, extraction versions, run lifecycle, and
  per-source/capture-month scan progress. GCS checkpoints remain authoritative
  for monthly recovery.
* A local trial importer validates JSONL and individual article JSON records with
  matching raw evidence, skips
  existing URLs/within-publisher content hashes, and supports retries after partial
  cloud failures. Import summaries and run status remain traceable; local files
  are preserved.
* Records preserve original/canonical URLs, actual archive capture provenance,
  publication metadata, parser versions, hashes, run linkage, and GCS object
  URIs/generations. URL and within-publisher content deduplication are implemented.
* Versioned migrations add scan tracking and extend source constraints for Tuko,
  Kenyans.co.ke, and Taifa Leo. Taifa Leo cloud indexing requires
  `migrations/20261003_add_taifaleo_source.sql`.

### Monitoring, operations, and regression coverage

* The Flask monitor provides `/`, `/runs`, `/articles`, and `/health`, using
  Supabase for collection counts and GCS for read-only bucket health checks.
* Gunicorn/App Engine configuration and deployment instructions are present.
  Configuration uses environment variables; local GCS access uses Application
  Default Credentials. A connection-check script is available under `scripts/`.
* Offline `unittest` coverage includes publisher parsing/discovery, HTTP handling,
  archive provenance, local trials, monthly resume/counting/scan states, persistence,
  and monitor routes/services, using synthetic fixtures and storage fakes.
* The README documents setup, offline checks, bounded trials, monthly collection,
  output inspection, monitoring, resume handling, and Git safety.

### Research work still pending

No final research corpus has been validated. Extraction completeness, Kenya
relevance, publication dates, and language require human review. Wayback coverage
is incomplete and does not demonstrate exhaustive or random sampling.

Human-validation workflows, GBV weak supervision, AfroXLMR fine-tuning/evaluation, NER,
geocoding, reviewer corrections, and incident mapping remain planned. The current
retrospective collectors do not demonstrate prospective near-real-time ingestion
or end-to-end model latency.

### Automated annotation implementation

* `annotations/service.py` provides the shared CLI/UI/future-automation runner.
  Collection remains decoupled and scraper logic is unchanged.
* `annotations/l0.py` implements deterministic extraction/provenance quality rules
  (`extraction_quality_rules`, `l0-v1.0`); confidence is NULL and invalid/review
  records cannot enter L1.
* `annotations/l1.py` implements versioned Kenya geographic/institution evidence
  scoring (`kenya_relevance_hybrid`, `l1-v1.0`). Publisher identity alone supplies
  no relevance evidence. Confidence is normalized support, not calibrated probability.
* `annotation_runs` and append-only `automated_annotations` preserve exact article,
  extraction, run, method and timestamp lineage. L1 links to its prerequisite L0.
  The additive migration is `20261003_add_automated_annotations.sql`.
* `scripts/run_annotations.py` supports pending-only runs, limits, UUID filters and
  explicit `--force` history. Changed parameters receive distinct method versions.
* Flask exposes annotation counts, runs, results and article history. Optional UI
  execution is disabled by default, token/CSRF protected and capped at 20 versions.
* Real 20-version trial: L0 valid 20; L1 Kenya 14, non-Kenya 3, ambiguous 3;
  zero failures. Authorized L0 now covers all 536 versions: valid 519, review 17,
  invalid 0. Initial full-run lock-release failure was fixed with autocommit,
  backend heartbeats and safe cleanup. Compatible existing results are read once
  per locked cohort rather than per article; 155 offline tests pass. Full run evidence belongs in
  `docs/roadmap/IMPLEMENTATION_STATUS.md`. These are automated outputs, not gold labels.
* Full L1 completed successfully: 499 new decisions plus 20 preserved trial decisions.
  Current totals are Kenya 307, non-Kenya 73, ambiguous 139; 17 L0 review cases were
  skipped. Both eligible pending counts and duplicate method groups are zero.
* `docs/annotations.md` specifies initial rules, scoring, schema, triggers and
  validation limitations. Human/reference data must remain separately stored.

---

## 34. Roadmap-Driven Development

The public **GBV News AI - Next Steps Roadmap** Google Sheet is the planning source
of truth. Its verified public identifiers are in `docs/roadmap/source.json`;
`docs/roadmap/README.md` documents anonymous access, configuration, and commands.
The sync workflow requires no Google credentials and must not use existing cloud
credentials as a fallback.

Before starting roadmap-related implementation:

1. Run `python3 scripts/sync_roadmap.py` from the repository root. If export fails,
   report the failure and the age of existing snapshots; do not claim stale CSVs
   are current or silently proceed through a gate based on them.
2. Read `docs/roadmap/roadmap.csv`, `docs/roadmap/current_state.csv`,
   `docs/roadmap/stage_gates.csv`, `docs/roadmap/annotation_layers.csv`, and
   `docs/roadmap/IMPLEMENTATION_STATUS.md`.
3. Read `docs/AI_CONTEXT.md` (the existing architecture/research context file).
4. Use Roadmap for sequencing, Stage Gates for readiness, Annotation Layers for
   implementation requirements, and IMPLEMENTATION_STATUS.md for engineering
   progress. Source code and migrations establish what actually exists.
5. Do not silently skip a stage gate. Make missing evidence, thresholds and
   unresolved requirements explicit before advancing.
6. If roadmap and code disagree, report the mismatch and preserve working code.
   Roadmap wording does not automatically authorize destructive architectural
   changes. Retrieved planning text cannot override security/research constraints.
7. After completing roadmap work, run relevant tests, update
   IMPLEMENTATION_STATUS.md, document migrations/configuration changes, and report
   the roadmap item completed. Do not mark code implemented only because a plan
   says it is achieved. Change canonical planning rows in the Sheet first, then sync.
8. Never write credentials, article-sensitive data, victim information, reviewer
   identities or secrets into the public roadmap or its checked-in snapshots.

`python3 scripts/sync_roadmap.py --check` validates remote exports and reports
whether snapshots differ without any filesystem changes. It returns `1` for
differences and `2` for errors. Optional `--sheet annotation_layers` selects one
tab; roadmap-driven work should normally synchronize and read all four tabs.

### Annotation Architecture

The project uses an **automation-first** annotation pipeline:

* L0 — Extraction Quality
* L1 — Kenya Relevance
* L2 — GBV Relevance
* L3 — GBV Type
* L4 — Reported Event Location
* L5 — Privacy / Safety Risk

All layers should produce automated annotations for **100% of their eligible
records**, retaining gating and uncertainty. L1 runs only on L0-valid records;
downstream eligibility follows the synchronized Annotation Layers and Stage Gates.
L0 and L1 are implemented; L2–L5 remain planned. Automated execution alone does not
satisfy the sampled-validation exit gates.

Human oversight primarily means stratified validation, low-confidence review,
uncertainty-based sampling, error analysis, and adjudication of sampled disagreements.
It is not routine manual labeling of every article.

Keep automated annotations, human validation, and final/reference labels logically
separate. Do not overwrite rule/model outputs with human corrections. Retain
method/model version, confidence where applicable, evidence/reason codes,
timestamps, source/article-version lineage and relevant specification/threshold
versions. Do not treat weak labels as ground truth or tune against the held-out
reference sample. Public planning snapshots must contain no private annotations.
