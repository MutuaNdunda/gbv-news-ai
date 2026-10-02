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
Annotation stratification and active learning are separate later stages.

This is retrospective archive collection. It does not implement prospective
continuous ingestion or demonstrate near-real-time discovery latency. The archive
corpus and its coverage limitations should be documented in the study methodology.

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

Taifa Leo support requires `migrations/20261003_add_taifaleo_source.sql` before
cloud indexing. Older all-source runs had six publishers; explicitly select those
original sources to retain their saved configuration when resuming. Taifa Leo's
local/CDX smoke trial scans at most 500 all-date results and is separate from the
monthly window. Its dated URLs and capture dates never substitute for publication
metadata. The legacy `en-US` template language is preserved as raw metadata and
flagged for review rather than treated as an article language label.

The default CDX query uses domain matching and ordinary rewritten HTML replay.
To compare the standalone Wayback trial's approach, add `--index-match prefix
--replay-mode original` with a new run name. Prefix mode queries `<domain>/*`
instead of including all subdomains; this is a change in discovery scope, not a
demonstrated performance improvement. Original mode requests the `id_` replay,
which avoids Wayback URL rewriting. Both modes retain publisher parsing, access
checks, publication filtering, cached paginated CDX discovery, and actual replay
capture provenance. Omitted options preserve legacy saved configurations; explicit
mode settings are recorded in the configuration and must match on resume.

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
