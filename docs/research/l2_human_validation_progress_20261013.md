# L2 human-validation review coverage — 13 October 2026

The researcher reported completing 400 human validations. A read-only,
repeatable-read database audit at **13 October 2026, 01:50:38 EAT** confirmed
complete recorded review coverage for one protected development-validation batch.
The audit used aggregate metadata only and rolled back its read-only transaction.
It fetched no article text, reviewer identities or per-article labels and made no
database, model, membership or review changes.

| Observed batch property | Result |
| --- | --- |
| Purpose | Development validation |
| Sampling strategy | Random |
| Pinned model | `l2-afroxlmr-dev-v1` |
| Protected from training | Yes |
| Requested / actual members | 400 / 400 |
| Members with initial / final review pointers | 400 / 400 |
| Resolved members | 400 |
| Pending initial reviews | 0 |
| Unable to determine / needs adjudication | 0 / 0 |
| Batch status | `in_review` |
| Completion timestamp | Unset |
| Members with revisions | 1 |
| Final-review article/version/prediction/guideline mismatches | 0 |

**Human-review recording is complete. Batch completion and independent performance
evaluation are separate steps.** The batch has not yet been marked `completed`,
and this documentation task did not run the evaluator or calculate metrics.
It does not assert final-test readiness, sampling approval or closure of the L2
research validation gate.

## Recorded evidence basis

The latest accepted-review pointers have these access notes:

| Recorded basis | Members |
| --- | --- |
| Bulk title-only decision; verified body not opened | 381 |
| Bulk verified body opened | 10 |
| Other or unspecified access notes | 9 |

The last group is not assumed to be title-only or fully read. Body access is not
proof of reading or understanding. Title-only decisions were explicitly permitted
by the researcher on 12 October; their evidence procedure differs from the original
full-context codebook instructions. Identify this distinction when interpreting
validation findings. Topic-based reason choices remain separate from GBV verdicts.

The frozen batch's guideline identifier is a checksum-based reference to
`docs/annotations.md`; this observation does not certify use of the codebook's
named `l2-gbv-relevance-codebook-v1.0` identifier. Preserve the pinned guideline
and review history and reconcile the actual instrument in the research record.
The 400-member batch should not be confused with all historical human-validation
rows: the same audit counted 703 L2 history rows and 11 L1 history rows, including
earlier reviews and revisions.

## Next operation

1. Inspect and accept the recorded decisions under the agreed research procedure,
   documenting title-only evidence, instrument identity, source/language support,
   prior exposure, duplicate-family handling and any required second review.
2. Use **Complete · freeze accepted decisions** on batch progress when the accepted
   decisions are ready. This updates the batch lifecycle; the agent did not perform it.
3. Run the existing private evaluator on the completed development-validation
   batch in a new private output directory. Preserve model, threshold, code and
   membership provenance; do not tune against protected references.
4. Report actual metrics and support only after evaluation and research checks.
   This aggregate audit did not recheck near-duplicate independence, sampling
   representativeness, language competence or full-text evidence quality.

See the [dataset operator guide](validation_dataset_creation.md),
[bulk review guide](../bulk_l2_validation.md),
[draft sampling protocol](l2_validation_sampling_protocol_v1.0.md) and
[implementation status](../roadmap/IMPLEMENTATION_STATUS.md).
All article content, identities, individual decisions and evaluation exports remain
private and must not be committed to Git or the public roadmap.
