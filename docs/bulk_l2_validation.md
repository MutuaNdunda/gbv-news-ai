# Bulk L2 human validation

Open **L2 Validation → a frozen batch → Bulk Review**. The existing local review
token, reviewer identity, guideline configuration and 30-minute signed session
are required. This interface works with existing frozen membership; it does not
create, resample or freeze a research batch. Single-article review remains available.

## Review a page

Choose 10, 20 (default), 50 or 100 articles per page. Filters are Unreviewed,
Reviewed (including recorded unresolved decisions), Needs adjudication and All
members. Server-side pagination and progress remain scoped to the selected batch.
Completed batches can be inspected but cannot be edited.

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

Record a concise independent reason for every decision. At the researcher's request
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
  1,000-character limit.
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
resume and immutable completion. `tests/js/validation_bulk.test.cjs` executes the
actual JavaScript handlers against a small DOM adapter for keyboard/inline controls,
lazy expansion, partial-save draft retention, explicit conflict refresh and
navigation guards. `tests/test_bulk_validation_js.py` runs these with Node.js as
part of offline discovery. Tests do not depend on cloud or model inference.
