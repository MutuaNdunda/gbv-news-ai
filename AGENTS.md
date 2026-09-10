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

Additional sources may be added later.

Each source should have its own scraper implementation rather than placing all publisher-specific logic inside one file.

---

## 4. Project Structure

The intended high-level repository structure is:

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
│   └── tuko.py
│
├── data/
│   ├── trials/
│   │   ├── raw/
│   │   │   ├── nation/
│   │   │   ├── citizen/
│   │   │   ├── kenyans/
│   │   │   ├── standard/
│   │   │   ├── star/
│   │   │   └── tuko/
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
│   └── models.py
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
├── .env
├── .gitignore
├── AGENTS.md
└── README.md
```

Agents may extend this structure when justified, but should avoid unnecessary complexity during the early research and MVP stages.

---

## 5. Trial Data Collection

All experimental and exploratory scraping should initially use:

```text
data/trials/
```

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

All collected data is local-only and must not be committed or pushed to Git. The
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

Common functionality may later be moved into shared modules such as:

```text
scrapers/
├── base.py
├── utils.py
├── nation.py
├── citizen.py
├── kenyans.py
├── standard.py
├── star.py
└── tuko.py
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

The web interface is expected to use Flask.

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

The current priority is the **data collection MVP**.

Focus should initially be on:

```text
1. Implement one reliable news scraper.
2. Collect trial articles.
3. Store raw trial results.
4. Normalize articles into a common schema.
5. Validate extraction quality manually.
6. Add additional publishers.
7. Introduce persistent database storage.
8. Develop annotation and weak-labelling workflows.
9. Fine-tune and evaluate AfroXLMR.
10. Add NER, geocoding, HITL, and visualization.
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
