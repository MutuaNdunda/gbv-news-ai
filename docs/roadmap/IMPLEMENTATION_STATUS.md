# Repository implementation status

This engineering log records executed code and observations. The public Sheet
remains the planning source of truth; synchronized CSVs were not edited manually.
No private article content, victim information or reference labels belong here.

## Current Milestone

**Automated Annotation Pipeline — L0 and L1: implemented; sampled validation pending.**

The Sheet's 407-record trial count is a planning snapshot. Live Supabase queries
on **3 October 2026 (Africa/Nairobi)** found **536 articles / 536 article versions**.
The user authorized L0 across all 536 after the successful 20-version L0/L1 trial,
then explicitly authorized L1 on all 499 remaining L0-valid versions. The 17 L0
review cases remain gated. Exact selected-version UUIDs are recorded privately
in each run's configuration.

## Completed

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
* L1 versioned 47-county geographic/institution evidence scorer
  (`kenya_relevance_hybrid`, `l1-v1.0`), conservative foreign/mixed/ambiguous handling,
  structured evidence and normalized confidence. Publisher identity supplies no score.
* L1 requires the exact current valid compatible L0. Invalid/review L0 cannot enter
  L1; L1-only execution does not implicitly execute L0.
* Append-only history, pending-only processing, force, parameter method identities,
  latest-compatible queries, advisory locking, failure isolation, per-version
  checkpoints/counters and structured secret-safe logs.
* Flask summary, run list/detail, filtered L0/L1 results and article history.
  Opt-in token/CSRF trigger is disabled by default and capped at 20 versions.
* Real bounded 20-version trial persisted both layers with zero failures; full L0
  subsequently covered all 536 versions. Default repeats added no duplicate decisions.
* Authorized full L1 completed: 499 new decisions, 17 gated review-case skips,
  zero failures and CLI exit 0. All 519 L0-valid versions now have L1 decisions.
* README, AGENTS, AI_CONTEXT, annotation specification and deployment notes updated.
* Follow-up roadmap sync found all snapshots current; all 152 existing tests passed.
  Existing-result reads were subsequently batched per locked cohort to remove
  per-article lookups, with forced dependency/version behavior unchanged.

## In Progress

Automated implementation and authorized L0/L1 execution are complete. Sampled
human validation remains pending; no human audit has been performed. Readiness
gates have not been passed through automated execution alone.

## Next

1. Inspect L0 anomalies by publisher and resolve extraction defects through versioned
   reprocessing, retaining flagged records and original evidence.
2. Reconcile the 407-record planning count with 536 observed versions; record exact
   membership for any smaller pilot.
3. Review initial rules/gazetteer and agree error thresholds, sample sizes and an
   uncertainty/stratification protocol. Engineering thresholds are not calibrated.
4. Inspect L1 ambiguity, evidence and source/language coverage over the eligible corpus.
5. Store sampled human validation and adjudicated reference labels separately;
   report accuracy/F1, false-pass/false-fail, ambiguity, calibration, subgroup errors
   and runtime before claiming research exit-gate completion.

L2–L5, AfroXLMR, NER, geocoding and mapping remain future work. Automated outputs
are not gold labels; execution alone does not satisfy sampled-validation gates.

## Blockers / Limitations

* No infrastructure blocker for the bounded trial or larger L0.
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

Anonymous sync and live `--check` succeeded on **3 October 2026 (Africa/Nairobi)**
before implementation; required headers matched and extra columns were retained.

| Snapshot | Planning rows | SHA-256 |
| --- | ---: | --- |
| `roadmap.csv` | 28 | `b88c01d909de866b70dea695e2d721545be50fcaeefa7aeedaa649a7241d6eac` |
| `current_state.csv` | 9 | `72fa241a1d9a07db7c6cf1056970308f28e4821bf8827316cdc474abcddf2f36` |
| `stage_gates.csv` | 12 | `c109802924997ce4fd73244192b00affb39b49de11788bd12b73a69f301229bd` |
| `annotation_layers.csv` | 8 | `b4142b6ae3e6638d4e8bc80f2381d51bd8c86631251b88063de8fc4d9f97a3d4` |

## Relevant Code / Migrations

* `annotations/{service,l0,l1,schemas}.py`, `annotations/resources/kenya_v1.json`.
* `database/models.py`, `database/repositories/annotations.py`.
* `migrations/20261003_add_automated_annotations.sql` — applied to development;
  other deployments must apply it separately.
* `scripts/run_annotations.py` — layers, limit, UUID filters, force, JSON summary.
* `app/services/annotation_service.py`, `app/routes/annotations.py`, annotation
  templates, article detail/history, navigation and opt-in app configuration.
* `storage/gcs.py` — optional generation-pinned JSON reads.
* `docs/annotations.md` — architecture, initial specification, CLI/UI, limitations.
* Existing roadmap/import/collection scripts and ingestion migrations retained.

## Test Status

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

### Current full-corpus coverage (verified after full L1)

| Layer | Current decisions | Label counts | Pending eligible versions |
| --- | ---: | --- | ---: |
| L0 | **536** | valid **519**, needs_review **17**, invalid **0** | **0** |
| L1 | **519** | kenya **307**, not_kenya **73**, ambiguous **139** | **0** |

Supabase contains **1,055** automated rows, no duplicate version/layer/method
groups and complete processed-generation metadata. The 17 quality-review versions
have no L1 result. These are automated outputs requiring sampled human validation.
The repeated combined pending-only command selected zero versions, persisted no
new annotation decisions and completed with exit 0.
