# Collection Runs: control and recovery

This change applies to `/runs`, the **collection** monitor, and to
`scripts/trial_scraper.py` and `scripts/collect_monthly.py`. Annotation runs at
`/annotations/runs` keep their existing execution/security/lease behavior. No
annotation, model, article or review history is rewritten.

## Installation and access

Apply `migrations/20261008_add_collection_run_control.sql` in filename order to
an intended development target before starting updated collectors. This is an
additive migration with nullable heartbeat, stop timestamp/reason, finalization
reason and per-attempt worker UUID, plus a partial running-heartbeat index. It
performs no historical status conversion. Schema installation is **not automatic**.
The monitor defers these fields on pre-migration targets and remains read-only;
restart it after migration so its cached readiness check refreshes.

For opt-in Stop controls, set private environment values:

```text
COLLECTION_CONTROL_ENABLED=1
COLLECTION_CONTROL_TOKEN=<private random token of at least 32 characters>
FLASK_SECRET_KEY=<private random signing key of at least 32 characters>
COLLECTION_STALE_SECONDS=1800
```

Use the same strong-token, signed-session CSRF and local-or-HTTPS control pattern
as annotation execution. The control token is entered into the password field;
it is never embedded in HTML or a URL. Every Stop submission requires it and CSRF.
A browser confirmation precedes POST `/runs/<uuid>/stop`; responses redirect 303.
No GET mutates database state or renews a worker heartbeat. Controls are disabled
by default. This adds cancellation only, not collection launch controls.

## Filtering and display

`/runs?status=running` filters both the count and paginated list in SQL. All is the
default; unsupported status input falls back to All. The filter form resets the
page, pagination links preserve status, and out-of-range pages redirect to the
last available page. Newest-started ordering and grouped article/scan counts are
preserved. Detail shows source/month scan progress and configuration; trial
source counters remain in the private GCS checkpoint rather than invented DB totals.

The list/detail show persisted status, last worker heartbeat, elapsed time,
indexed article counts, completed/total scans and a separate operational badge:

- **Running:** recent heartbeat.
- **Stop requested:** request persisted; worker has not necessarily ended.
- **Possibly stalled:** no heartbeat, or heartbeat older than the display threshold.

Possibly stalled is derived, never persisted and never evidence of failure by
itself. Long legitimate network/storage work may temporarily show it. Historical
and already-running older workers have no managed attempt identity and cannot
honor UI cancellation; their UI says worker control is unavailable. Use their
original terminal for Ctrl-C where still active. Local trial import is not newly
made a managed/cancellable worker by this change.

## Status meanings

| Persisted status | Meaning |
| --- | --- |
| running | Current worker attempt owns execution and is expected to progress. |
| completed | Trial finished under its configured bounded scope; not exhaustive collection or research validation. |
| interrupted | Ctrl-C, cooperative Stop, process interruption or proven-orphan reconciliation ended work before normal completion. |
| failed | Unrecoverable execution/checkpoint failure. User Stop is not failure. |
| paused_index_unavailable | Monthly execution intentionally paused after three consecutive index failures. |
| finished_with_gaps | Bounded execution finished with known gaps/errors; not complete archive coverage. |
| index_scans_finished | Monthly scans exhausted the configured capture-month index scope without known gaps; not exhaustive publication coverage. |

## Worker lifecycle

Both collector entrypoints acquire the existing PostgreSQL run-name advisory lock
**before** resolving/resuming a row, including programmatic calls. CLI mains no
longer acquire a second lock. Use direct PostgreSQL or session pooling; the known
transaction-pooler port is rejected. The lock connection is autocommit and checks
its original backend ID and exact `pg_locks` key. It never reconnects/relocks after
loss. Release failures are logged safely and cannot overwrite a durable terminal
status.

Resume keeps the same run ID, exact configuration and existing data/counters;
a new attempt UUID fences heartbeat and finalization updates. Previous request
fields are cleared so a deliberate resume can proceed; interrupted progress retains
its prior safe stop reason in GCS until a new interruption overwrites it. The prior
terminal state is otherwise updated as under the existing resumable run semantics;
this is not a new append-only execution-attempt ledger.

Workers check control at source/month boundaries, pending-index retries, iterator
steps, around index/article requests and immediately before normalized persistence.
The shared HTTP helper also checks listing/discovery/robots/redirect requests and
retries. Ordinary polls are limited to once per **30 seconds**; forced boundaries
recheck stop/ownership but heartbeat writes remain limited to 30 seconds. A
heartbeat means worker activity, not necessarily newly saved articles. There is
no background scheduler or heartbeat thread. On the main thread, SIGTERM sets a
cooperative shutdown flag; the next safe checkpoint records `process_shutdown`
and ends as interrupted. The previous signal handler is restored afterward.
SIGKILL, machine shutdown and process crashes cannot run cleanup and require
later ownership-checked reconciliation.

Stop leaves status `running` and records timestamp/reason atomically and
idempotently. The worker raises cooperative cancellation through the Ctrl-C
checkpoint path, writes final counters/progress, and finalizes `interrupted` with
`user_requested_stop`. An unfinished monthly scan returns to `pending`, retaining
its counters and start time for resume. Already durable articles remain indexed.
An in-flight article persistence operation finishes as one safe unit rather than
aborting between processed storage and indexing. Network requests and storage
calls are not forcibly aborted; cancellation waits for a safe boundary. An
HTTP read timeout can be up to the configured 300 seconds, and retries/pacing or
storage latency can further delay observation; Stop is not instantaneous.

The shared execution boundary covers setup, pending-index recovery and zero-work
runs as well as the main loops. An emergency checkpoint retains the actually loaded progress/pending-index
state when setup/recovery exits before the inner handlers. Database finalization
runs even after GCS reporting fails, recording `failed`/`execution_or_checkpoint_failed` rather than claiming
success. On lost ownership, guarded GCS/scan/article writes fail closed; the old
worker cannot finalize a successor's row. If DB finalization is unreachable or
lease ownership cannot be verified, the row stays available for later diagnosis.
Cross-service writes cannot be atomically cancelled after they are already in
flight; immutable raw/processed objects and existing retry lineage remain in use.

## Diagnostics and reconciliation

Run read-only diagnostics first:

```bash
.venv/bin/python scripts/reconcile_runs.py
.venv/bin/python scripts/reconcile_runs.py --dry-run --stale-seconds 1800
```

The default never changes rows or GCS. It lists running run IDs/start times,
heartbeat, saved/indexed counts and scans, and probes the **actual collector lock
key**, briefly acquiring/releasing it when free. A free lock is an observation,
not proof that a legacy process is dead. Before migration, a legacy SQL diagnostic
reports missing columns and never infers staleness from start time or scan activity.

Explicit repair, after inspecting the diagnostic:

```bash
.venv/bin/python scripts/reconcile_runs.py --apply --stale-seconds 1800
```

A row qualifies only when all are true:

1. It is still `running`.
2. It has an updated-worker attempt UUID and a real heartbeat.
3. Its heartbeat is strictly older than the threshold (default 1,800 seconds).
4. The maintenance process acquires the same run-name lock, verifies ownership,
   and rechecks current row state/heartbeat under a row lock.

Repair sets `interrupted`, the existing `finished_at`, and
`finalization_reason=stale_run_reconciled`. It resets running scan statuses to
`pending` while preserving all counters, identities, provenance and data. It
leaves terminal rows, fresh rows, active owners and missing-evidence legacy rows
untouched. Repeating repair is idempotent. GCS checkpoints are not rewritten by
maintenance; the database records the repaired lifecycle and normal exact-config
resume continues from retained GCS progress. No GET invokes reconciliation.

## Read-only development observation — 8 October 2026

A diagnostic against the configured development database found **one** running
collection row: `multi_publisher_wayback_gbv_500`, started **7 October 2026,
14:10:30 EAT**, with zero indexed article versions and zero scan rows. No advisory
owner was found at the probe. All five new control fields were absent, so heartbeat
and managed-attempt evidence were unavailable. **No row was repaired**, no migration
was applied, and no collector was started by this diagnostic. These counts are not
GCS artifact totals or proof of a process's death.

## Change inventory and validation

Exact files changed/added for this task:

| Area | Files |
| --- | --- |
| Configuration and project guidance | `.env.example`, `AGENTS.md`, `README.md` |
| Flask configuration and collection routes | `app/__init__.py`, `app/routes/runs.py` |
| Collection query/display service | `app/services/run_service.py` |
| Collection UI | `app/templates/runs/index.html`, `app/templates/runs/detail.html`, `app/templates/runs/_stop.html`, `app/static/js/collection-runs.js` |
| Shared collector execution | `collection/__init__.py`, `collection/lifecycle.py` |
| Models/repositories | `database/models.py`, `database/repositories/collection_runs.py`, `database/repositories/collection_run_scans.py` |
| Migration | `migrations/20261008_add_collection_run_control.sql` |
| Worker and maintenance entrypoints | `scripts/trial_scraper.py`, `scripts/collect_monthly.py`, `scripts/reconcile_runs.py` |
| Request and durable-write guards | `scrapers/common.py`, `storage/gcs.py`, `storage/persistence.py` |
| Synthetic tests/fakes | `tests/test_collection_control.py`, `tests/test_monitor.py`, `tests/test_monitor_services.py`, `tests/storage_fakes.py` |
| Operational documentation | `docs/collection_run_control.md`, `docs/AI_CONTEXT.md`, `docs/roadmap/IMPLEMENTATION_STATUS.md` |

The 28 new offline regressions execute real SQL filtering/counting/pagination,
intent-only/idempotent/terminal-safe Stop, stale/no-owner/fresh/active/missing-
evidence reconciliation, state rechecking and counter preservation, UI security
and display, pre-migration monitoring, heartbeat cadence and attempt identity,
saved-work-preserving worker Stop, final-request Stop, zero-work success, Ctrl-C,
unexpected/setup/recovery/checkpoint failures, cooperative SIGTERM, lost leases, backend changes, transaction-
pool rejection and post-completion lock-release errors. SQLite tests establish
query/workflow behavior; mocked lease tests plus the read-only development probe
do not establish a new live PostgreSQL installation or production deployment.

Final validation on 8 October 2026:

- `.venv/bin/python -m unittest discover -s tests -q`: **382 tests run, 381 passed,
  one optional installed-model integration test skipped**, zero failures.
- `git diff --check`: passed.
- `git ls-files data`: empty; no collected artifacts tracked.

No collected datasets, secrets, model weights or temporary diagnostics were
committed. Stop is disabled until private configuration enables it; the new
migration and updated workers must be in place before it can operate. No live
Stop request or repair was sent in this task.
