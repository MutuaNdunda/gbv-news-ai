# Bulk L2 human validation

## Model Performance status — 13 October 2026

`L2-VALIDATION-V1` was completed on **13 October 2026 at 16:19:19 EAT**; its first private development-validation report was generated at **16:22:39 EAT**.

The sealed batch can be inspected but cannot be revised through bulk review.
Model comparisons live in the separate protected researcher dashboard, not the
blind cards. Do not create another batch merely because the historical milestone
below still describes in-review progress. See [the dashboard guide](l2_model_performance_dashboard.md).

The 400 accepted workflow decisions contain 342 binary references and 58 semantic borderline exclusions. Title-only evidence (381/400), frozen-instrument reconciliation, publisher scope, unverified language metadata and near-duplicate risks remain interpretation limits. A completed batch and a private report do not establish a gold standard or close the research gate.

Open **L2 Validation → a frozen batch → Bulk Review**. The existing local review
token, reviewer identity, guideline configuration and 30-minute signed session
are required. This interface works with existing frozen membership; it does not
create, resample or freeze a research batch. Single-article review remains available.

**Historical pre-completion coverage — 13 October 2026:** one protected development-validation
batch then had 400/400 resolved saved reviews and zero pending, confirmed read-only
at 01:50:38 EAT. At that audit its status was `in_review`; completing the accepted batch and
running private evaluation are separate steps. See the
[progress report](research/l2_human_validation_progress_20261013.md). Do not equate
the saved-review counter with frozen acceptance or measured model performance.

## Review a page

Choose 10, 20 (default), 50 or 100 articles per page. Filters are Unreviewed,
Reviewed (including recorded unresolved decisions), Needs adjudication and All
members. Server-side pagination and progress remain scoped to the selected batch.
Completed batches can be inspected but cannot be edited.

Each article displays **Article not reviewed** until this batch member has a saved
human decision. Reviewed articles display **Article reviewed**, **Reviewed by** and
the human **Verdict**. The latest accepted revision supplies the reviewer and verdict;
drafts and failed saves never change the saved status. Successful bulk saves update
the card immediately, and the same status appears on the protected single-article
validation page. Unsure and Needs adjudication are shown explicitly. These summaries
remain scoped to frozen membership and expose no model answers.

For example: **Article reviewed · Reviewed by: [saved reviewer] · Verdict: Not GBV**.
The displayed reviewer is the server-configured identity recorded with that saved
decision, not an authenticated user account or the current configuration value.
The member's accepted final-review pointer supplies this summary; reviews elsewhere
do not silently change this batch's decision. Choose **Reviewed** or **All members**
to revisit saved cards, since the default **Unreviewed** filter omits them after
reloading. Save remaining drafts before refreshing to load an updated interface.

Headlines, source, publication date, unvalidated language metadata, logical article
ID and extraction-version ID appear in compact cards. **Read article** expands the
exact stored extraction on demand. Page loads never retrieve bodies. Expansion
uses the existing generation-pinned GCS loader and checks extraction lineage and
body hash. Text is inserted using `textContent`, not HTML.

Inline choices use the existing vocabulary:

| Control | Stored human meaning |
| --- | --- |
| GBV | `gbv` |
| Not GBV | `not_gbv` |
| Borderline relevance | Semantic `borderline` |
| Unsure / insufficient evidence | `unable_to_determine`, NULL human label |
| Needs adjudication | `needs_adjudication`, NULL human label |
| Skip | No review or semantic label |

Select an independent reason for every decision and optionally add details:

| Reason option | Intended use |
| --- | --- |
| Local politics | Political reporting in the local context |
| Clear reported GBV incident | Reporting with clear evidence of a reported GBV event |
| Other local news | Other domestic news topics |
| International news | Reporting about events outside Kenya |
| GBV-related reporting (policy, prevention or commentary) | Substantive GBV coverage beyond a specific incident |
| Sports news | Sports reporting |
| Insufficient evidence / unclear relevance | Evidence is inadequate for a confident decision |
| Other reason | A rationale outside the listed categories |

Choose the human verdict independently. A politics, international or sports topic
can still contain GBV; choosing a reason never assigns or changes the verdict.
Additional details are optional for every category, including Other reason, and
are limited to 900 characters. The server stores the readable category followed
by any details in the existing review-reason field. Missing/unknown categories or
invalid details fail that row; failed drafts retain both inputs. Older free-text
reasons and open forms remain supported, and saved history is unchanged.

At the researcher's request
on 12 October 2026, GBV, Not GBV and Borderline can be saved from the title alone.
Opening verified article text is optional; use it when the headline provides
insufficient context, or record an unresolved decision. Existing
`human_validations.notes` explicitly distinguishes title-only resolved decisions,
verified body access, and unresolved decisions without body access. Body access
does not prove reading or understanding. This changes the bulk interface's earlier
full-text requirement; it does not revise the finalized codebook. Document the
review evidence procedure before interpreting evaluation results. No new semantic
labels or schema columns are introduced.

Shortcuts affect the highlighted row: **G** GBV, **N** Not GBV, **U** Unsure,
**J/K** next/previous row, **Space** expand/collapse. Shortcuts are disabled in
inputs, textareas, selects and dialogs, with modifier keys, or while saving.

## Save and resume

**Save Selected Labels** sends only actual draft decisions. Skips remain unsaved.
Successful reviews are appended; failed rows retain their selections and reasons.
The save summary includes the reason and affected row count, rather than only a
failure total. A failed reason or storage check retains valid body-access receipts;
only a saved revision or stale-member conflict invalidates the previous pointer's
access receipt. Correcting a reason does not require opening verified content again.
Saved counters update only after successful persistence. Unresolved human reviews
count as recorded initial decisions, not resolved binary references.

The server locks/prefetches batch members, annotations, extraction versions and
latest review history in bounded queries. Per-row savepoints isolate invalid
decisions while committing valid ones in the enclosing transaction. Results are
returned only after commit. A whole-transaction/storage failure reports an error
and retains browser drafts; check current saved versions before retrying when a
response is lost. The member's expected final-review pointer prevents duplicate
retries from appending another decision.

Conflicting rows expose **Refresh saved version · keep draft**. This explicitly
loads the current human decision and preserves the proposed revision. Reconsider
the draft against that decision and document the revision before saving. Initial
decision pointers remain immutable; permitted revisions append history and update
only the final pointer. Revisions can also be title-only. Completed references stay immutable.

Return to Unreviewed or **Continue from first unreviewed** to resume saved progress.
Drafts are memory-only; there is no draft autosave or local-storage persistence.
Navigation, reload and closing the page warn when drafts remain. To recover an
expired session, leave the draft page open and unlock from batch progress in another
tab before retrying. A browser crash can still lose unsaved drafts.

## Security, limits and routes

- Page: `GET /annotations/validation/<batch_id>/bulk`.
- Body: `GET /annotations/validation/<batch_id>/bulk/<member_id>/body`.
- Save: `POST /annotations/validation/<batch_id>/bulk/save`.
- Direct localhost authenticated access is enforced for all three endpoints.
- Saves require a dedicated signed-session CSRF token, at most 100 unique rows,
  at most 200,000 decoded JSON characters, and a 1,200,000-byte request limit.
  Other endpoints retain their existing 16 KiB limit. Reasons retain the existing
  1,000-character limit; new optional details are capped at 900 characters so the
  selected category and details fit together. Submitted categories are checked
  against the shared reason list.
- Signed, 30-minute body-access receipts bind the batch, member, extraction/hash,
  final-review pointer, reviewer identity and guideline. Tampered/stale receipts
  cannot be recorded as verified body access. Submitted invalid receipts still fail
  closed; reopen the body after expiry or revision. An empty receipt permits a
  title-only resolved decision and records that basis.
- HTML/JSON use private/no-store responses. Bulk projections and body/save responses
  omit all machine labels, probabilities, thresholds, weak evidence and agreement,
  including after a human decision. No model is loaded or invoked.

No migration, dependency or new environment variable is required. Existing review
and validation schema readiness and protections remain prerequisites. No model,
threshold, frozen membership, real human label or independent metric is generated
by implementing this interface. Sampling approval, near-duplicate checks, reviewer
competence and independent adjudication remain governed by the existing protocol.

## Verification

`tests/test_bulk_validation.py` exercises real synthetic Flask/SQL pagination,
lazy content, blinding, lineage/history, 100-row persistence, query-count bounds,
partial failures, conflicts, duplicate retries, skips, receipt checks, access,
resume and immutable completion. Review-status regressions verify pending status,
latest reviewer/verdict after revisions, escaped identities and final-test blinding.
Reason regressions verify every option, optional details, server-side rejection,
verdict independence and single-article error retention.
`tests/js/validation_bulk.test.cjs` executes the
actual JavaScript handlers against a small DOM adapter for keyboard/inline controls,
lazy expansion, immediate saved-status updates, partial-save draft retention, explicit conflict refresh and
navigation guards. `tests/test_bulk_validation_js.py` runs these with Node.js as
part of offline discovery. Tests do not depend on cloud or model inference.
