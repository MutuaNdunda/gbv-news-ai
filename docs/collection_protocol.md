# January–August 2026 archive collection

The collection window is **1 January–31 August 2026, inclusive**. Discovery scans
archive capture months from August backwards to January, for Nation, Citizen,
Standard, Star, Tuko, Kenyans.co.ke, and Taifa Leo in each month. Publication metadata, rather than capture or
retrieval time, determines whether an article belongs in this corpus and which
monthly count it contributes to. The stated publication calendar date is retained;
unknown timezones are not silently converted to UTC.

## Sampling and scope

Collect broad reporting candidates from the seven registered publishers, without gender or
GBV keyword selection. Every record still needs Kenya-relevance and extraction
quality review. The 5,000 target in the proposal is a minimum **annotated** corpus,
including GBV and non-GBV reporting; it is not an ingestion stopping rule.
Annotation and validation are separate downstream workflows; automated L0/L1,
L2 weak supervision, local review and the first real AfroXLMR development model
now exist. Seeded independent/diagnostic batch sampling, blinded first review,
protected membership and private evaluation are implemented; no real reference
batch or active-learning cycle has been executed. Use the
[validation dataset-creation guide](research/validation_dataset_creation.md).

This is retrospective archive collection. It does not implement prospective
continuous ingestion or demonstrate near-real-time discovery latency. The archive
corpus and its coverage limitations should be documented in the study methodology.

## Current handoff to validation — 8 October 2026

The read-only audit beginning 22:50 EAT observed 2,119 article versions and complete
compatible eligible L0/L1/model coverage. It did not establish exhaustive archive
coverage or validated labels. Formal-source independent metadata screening finds
1,089 candidates, with Standard zero, before GCS/language/period/near-duplicate
and exposure checks. Historical collection counts are not a current sampling frame.
Agree the validation design and address missing source support before freezing.

Updated cloud trial/monthly collectors require the additive collection-control
migration; it remains uninstalled on the observed development target. Existing
validation-batch schema is separately ready. See
[collection run control](collection_run_control.md) for safe Stop, heartbeat,
explicit orphan repair and preserved exact-config resume semantics.

## Running

```bash
python3 scripts/collect_monthly.py \
  --start-month 2026-01 --end-month 2026-08 \
  --run-name jan-aug-2026
```

There is no default article or index-page cap. The crawler works sequentially with
at least a two-second request interval, robots checks, timeouts, and limited retries.
The same command resumes that run: completed scans are skipped and stored URLs and
within-publisher text hashes prevent duplicate insertion. Do not run two processes
against the same run name; Supabase advisory locking rejects concurrent use. Add
`--max-index-pages 1 --max-fetches-per-month 2`. These limits apply to each
publisher/capture-month scan and are recorded as incomplete coverage, not success.

`--source citizen` (repeatable) restricts publishers. Valid keys are `nation`,
`citizen`, `standard`, `star`, `tuko`, `kenyans`, and `taifaleo`. Resume requires the same
configuration; choose a new run name to change limits or dates. Existing articles
and extraction versions remain deduplicated across runs.

Trial CLI defaults to shared waybackpy historical discovery for all seven registered
publishers; `--sources` selects one or several. Their own domain, prefix, article-route
and extraction adapters remain authoritative. `--method live` is an explicit current
publisher-listing/URL path, without automatic fallback after archive failures.
Repeatable `--term` arguments OR-match escaped, case-insensitive original URL text,
including hyphenated or encoded spaces. They do not search titles/bodies or assign
GBV labels. URL enrichment can miss relevant reports and underrepresent Swahili
or differently worded URLs; use it as diagnostic enrichment alongside broad
sampling, not the sole research sampling frame. Classification remains downstream.

`--from-date`/`--to-date` are capture bounds; `--publication-start`/`--publication-end`
independently gate extracted dates. One newest/oldest capture is selected among
bounded observed records per normalized publisher/article identity. Partial scans
cannot establish the full archive's newest/oldest capture. `--max-records`,
`--max-index-requests`, `--max-attempts` and successful-save `--limit` apply separately
to each publisher; page bounds apply per query. Counters/stopping reasons distinguish
empty coverage, duplicates, extraction failures and configured bounds. Selected
publisher failures are reported while others continue. See README for exact commands.
Returned but rejected records receive `no_valid_candidates`; this is distinct from
an empty filtered query. The actual seven-publisher smoke saved five Citizen and
five Kenyans.co.ke articles. Four other sources hit CDX timeouts, while Taifa Leo's
returned section-prefixed routes were outside the existing root-slug/dated-story
validator. These failures do not establish absent archive coverage. Modern layouts
and unsupported routes remain publisher-specific extraction limitations.

Taifa Leo support requires `migrations/20261003_add_taifaleo_source.sql` before
cloud indexing. Older all-source runs had six publishers; explicitly select those
original sources to retain their saved configuration when resuming. Taifa Leo's
local/CDX smoke trial scans at most 500 all-date results. Its cloud trial counterpart
can follow continuation pages with `--max-pages N`, each capped at 500 index rows;
`--limit` bounds new saved articles per invocation. Both are separate from the
monthly window and require publication-date and extraction review before corpus
inclusion. Cloud trial reruns deduplicate indexed articles but revisit discovery
from its first page. Its dated URLs and capture dates never substitute for publication
metadata. The legacy `en-US` template language is preserved as raw metadata and
flagged for review rather than treated as an article language label.

The monthly collector's default CDX query uses domain matching and ordinary rewritten HTML replay.
To compare the standalone Wayback trial's approach, add `--index-match prefix
--replay-mode original` with a new run name. Prefix mode queries `<domain>/*`
instead of including all subdomains; this is a change in discovery scope, not a
demonstrated performance improvement. Original mode requests the `id_` replay,
which avoids Wayback URL rewriting. Both modes retain publisher parsing, access
checks, publication filtering, cached paginated CDX discovery, and actual replay
capture provenance. Omitted options preserve legacy saved configurations; explicit
mode settings are recorded in the configuration and must match on resume.

The index read timeout is configurable with `--index-read-timeout` (default 30
seconds per attempt; accepted range 1–300). For example, `--index-read-timeout 120`
allows slower CDX responses. This operational wait may change on an existing run
without changing its discovery configuration or cached query keys. The UTC start
time and timeout of each invocation are retained in `progress.json` under
`execution_settings` and the timeout is logged. Connection waits remain 10 seconds;
robots-policy and article-replay read waits remain 30 seconds. Retries remain capped
at three, so a longer timeout also increases time spent on unavailable services.
HTTP 504 is an upstream gateway failure that cannot be repaired by a larger client
timeout; preserve the paused checkpoint and retry later rather than treating failed
discovery as empty coverage. No live fallback or discovery-scope change is automatic.

HTTP 429 and transient server errors have at most three attempts, honoring valid
`Retry-After` seconds or dates. Waits above 60 seconds defer the request as a failure
without an early retry. Access denials are not retried. Smoke tests may exit with
code `2` because their configured limits intentionally leave incomplete coverage;
inspect scan states and logs to distinguish limits from retrieval failures.

## Outputs

- `gs://<GCS_RAW_BUCKET>/<publisher>/<capture-year>/<capture-month>/<article-id>/<raw-content-hash>.html`: original HTML,
  persisted before parsing.
- `gs://<GCS_PROCESSED_BUCKET>/<parser-version>/<publisher>/<year>/<month>/<article-id>/<content-hash>.json`:
  normalized JSON with dates and provenance.
- `gs://<GCS_RUNS_BUCKET>/runs/<run-name>/monthly_counts.csv`: 56 rows for seven publishers across eight months, ordered August to January, containing
  publisher, publication month, newly saved articles for the run, and total stored
  articles for the requested window. Counts include unreviewed candidates, not
  confirmed GBV articles or incidents.
- `gs://<GCS_RUNS_BUCKET>/runs/<run-name>/collection.log`: retrieval events and summaries.
- `gs://<GCS_RUNS_BUCKET>/runs/<run-name>/progress.json`: configuration, scan status,
  counters, missing dates, out-of-window articles, and progress timestamps.
- `gs://<GCS_RUNS_BUCKET>/runs/<run-name>/cdx-cache/*.cdx.json`: cached responses for traceability and
  reduced requests on restart. Each article preserves the original CDX query URL.

Supabase `collection_runs` tracks lifecycle/configuration, `articles` holds logical
source/canonical identities, and `article_versions` records exact extraction lineage,
run linkage, provenance, processing status, and GCS URIs/generations.
Each monthly source/capture-month state is also idempotently mirrored into
`collection_run_scans`. Its status and counters are updated whenever the corresponding
GCS progress/report checkpoint is written, making operational progress queryable
without reading run artifacts. GCS remains authoritative for checkpoint recovery.

An August capture can contain a January publication: it contributes to January's
count. `same_month_capture_scan` describes index scanning, not completeness of
that publication month's news. Pending and failed scans must not be interpreted
as months with no published articles. Three consecutive index failures pause the
run and preserve all remaining months as pending. Rerun the same command to retry.

## Coverage limits

Wayback's CDX index lists archived captures, not every article a publisher published.
This implementation queries successful HTML captures during January–August 2026,
accepts publisher-specific article URL patterns, and follows CDX continuation keys.
It keeps one indexed capture per URL per scan and rejects live or off-publisher
redirects. Actual replay capture times remain in article metadata.

Articles first archived after August, missing archive records, restricted articles,
unsupported historical layouts, and missing publication dates can cause omissions.
Missing-date records are logged and excluded from month counts rather than assigned
a month from their URLs or archive timestamps. No claim of exhaustive publisher
coverage or random sampling is made. The date-window filter is automatic, but
Kenya relevance and language coverage still require human validation.

## Annotation handoff — verified 6 October 2026, 00:04 EAT

Collection remains independent of classification and never selects the corpus
solely from GBV keywords. The dated pre-expansion development readback contains 536 extraction
versions: L0 valid 519/needs_review 17; L1 v2 kenya 324/not_kenya 35/ambiguous 160.
L2 weak bootstrap covers the 324 compatible L1-Kenya versions, with 7 gbv,
15 not_gbv and 302 borderline. These are provisional research candidates and
automated labels, not verified incidents, a gold corpus or coverage/accuracy claims.

Protected local Human Review supports L0/L1/L2 and preserves exact extraction,
machine annotation and human revision lineage. The first real AfroXLMR development
artifact is locally configured; operational closure verified 324/324 compatible
predictions (11 gbv / 307 not_gbv / 6 borderline), with zero pending. The resume
added 24 rows while preserving prior model/weak/human/upstream history. Human overlay on the separate weak cohort is 10/312/2. Mixed training
uses 322 binary records, only 10 positive (three reviewed), and no frozen independent
reference set exists. Operational progress is not independent model evaluation.
The L2 constraints/index/trigger are installed and behavior-tested in development;
verify other targets independently before L2 writes. Structured validation batches,
initially hidden predictions, protected membership and private evaluation are
implemented; separate adjudication records remain future work. The researcher
confirmed L2 codebook v1.0 finalization on 7 October. Next, agree sampling/support
and review-acceptance policy, verify the unseen expanded pool, and execute the
first protected validation batch. Codebook completion does not establish a
completed reference set or independent scores. Source/language strata must account for the archive and
metadata limitations above; training-article reviews cannot establish independent
model performance. See [the remaining validation work](annotations.md#17-next-steps-future-work).

Use [the annotation specification](annotations.md), [operator commands](../README.md)
and [dated implementation evidence](roadmap/IMPLEMENTATION_STATUS.md) for downstream
processing and sample validation. They do not resolve the archive omissions or
language/publication-date limitations described above.
