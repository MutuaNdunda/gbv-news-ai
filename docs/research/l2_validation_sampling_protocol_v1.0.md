# L2 Validation Sampling Protocol v1.0

| Metadata | Value |
| --- | --- |
| Version | 1.0 |
| Status | **Draft for supervisor/research approval** |
| Research layer | L2 — GBV Relevance |
| Applicable development model | Exact pinned `l2-afroxlmr-dev-v1` |
| Unit of analysis | Eligible digital-news article, represented by its pinned extraction version |
| Formal publishers | Daily Nation; The Standard; The Star; Citizen TV; Taifa Leo |
| Formal languages | English; Swahili; Sheng; English–Swahili and other evidenced Kenyan code-switching |
| Owner | Project researcher; named owner to be recorded in the approval record |
| Approval status | Pending; no supervisor approval is asserted |
| Draft prepared | 7 October 2026 |
| Effective date | **Pending approval** |
| Proposed first batch | `L2-VALIDATION-V1` — `development_validation` |
| Semantic standard | [L2 GBV Relevance Codebook v1.0](l2_gbv_relevance_codebook_v1.0.md) |

**Status update — 7 October 2026:** the researcher confirmed that the companion
L2 codebook v1.0 is finalized. This protocol remains a draft: sampling size/design,
review acceptance, support and execution controls have not been confirmed as
completed. Codebook finalization alone does not create `L2-VALIDATION-V1` or
establish independent metrics.

## 1. Objective, authority and present status

Obtain the first defensible, independent human-reference assessment of the development model's L2 article relevance decisions. Distinguish representative assessment of an explicitly defined unseen eligible frame from diagnostic error exploration. This first batch is **development validation, not the final thesis test**. No independent accuracy, precision, recall, F1, calibration or multilingual fairness result is established by this draft.

The researcher's updated instruction specifies five formal publishers. The [codebook scope](l2_gbv_relevance_codebook_v1.0.md#1-authority-scope-and-limits) explains proposal provenance and unresolved Citizen TV/Citizen Digital mapping. Repository summaries do not establish supervisor approval or an ethics amendment. This draft does not authorize collection, inference, batch creation, human review or evaluation.

Implementation was cross-checked against [sampling/evaluation functions](../../annotations/validation_batches.py), [batch storage and readiness](../../database/repositories/validation_batches.py), [human-review contracts](../../annotations/validation.py), [local validation routes](../../app/routes/validation.py), [export exclusions](../../annotations/l2_datasets.py), [training](../../annotations/l2_training.py), and [the validation migration](../../migrations/20261006_add_l2_validation_batches.sql). [Annotation documentation](../annotations.md#22-l2-validation-and-protected-reference-workflow) describes operator behavior; [the engineering log](../roadmap/IMPLEMENTATION_STATUS.md) records dated execution.

At initial drafting on 7 October, a read-only roadmap check found snapshot differences.
Subsequent synchronization refreshed the four exports; the current documentation
update's sync returned all four current. The public combined codebook/workflow
task still reads `In progress`; Markdown records the newer researcher-confirmed
codebook completion separately. No manual CSV edit or public Sheet write was made.

### Dated engineering baseline, not validation findings

The following are documented 5–6 October observations, not a fresh database audit or five-publisher/language breakdown:

| Engineering observation | Recorded state | Interpretation |
| --- | --- | --- |
| Collected article versions | 536 | Seven-source engineering corpus, not a validated final population |
| Automated L0 | 519 valid; 17 review | Extraction gates still require validation |
| Current L1 v2 | 324 Kenya; 35 non-Kenya; 160 ambiguous | Automated geographic decisions, not independent truth |
| Original L2 weak labels | 7 `gbv`; 15 `not_gbv`; 302 `borderline` | Original weak outputs remain preserved |
| Effective weak/human overlay | 10 / 312 / 2 | 300 corrections and two confirmed borderline among the original borderline cases; 22 original binary weak results unreviewed |
| Actual dev-v1 training | 322 mixed-effective binary records: 10 / 312 | Only three positives human-reviewed; **all 322 are training-exposed** |
| Model predictions | 324 compatible: 11 / 307 / 6; zero pending | Operational coverage, not measured correctness |
| Validation schema | Installed and behavior-verified in development on 6 October at 23:48 EAT | Target-specific readiness; not installation proof elsewhere |
| Independent validation | No real batch or independent metrics generated in the documented engineering milestone | No research acceptance claim |

Given that recorded 324-member engineering cohort and its 322 training members, **at most two** versions could remain before formal-source filters, eligibility rechecks, duplicates and protection exclusions. This is a conditional upper bound, not a current pool measurement. The two excluded semantic borderline cases were already human-reviewed at the weak layer; if they are the remaining candidates, prior researcher exposure also limits any claim of pristine blinding. Verify the actual unseen frame privately before a later authorized batch. Do not score the training cohort and call it independent. Meaningful validation will likely require separately authorized collection of additional real, unseen articles.

## 2. Formal population and operational sampling frame

| Formal publisher | Required source key |
| --- | --- |
| Daily Nation | `nation` |
| The Standard | `standard` |
| The Star | `star` |
| Citizen TV | `citizen` — Citizen Digital digital articles; mapping requires documentary confirmation |
| Taifa Leo | `taifaleo` |

The proposed formal assessment is restricted to these five publishers. Set the source filter explicitly to **`nation,standard,star,citizen,taifaleo`**. Tuko (`tuko`) and Kenyans.co.ke (`kenyans`) may be used in separately named engineering/diagnostic work, but do not pool their outcomes into formal thesis estimates without an approved scope amendment. The app accepts all seven source keys and a blank filter means all sources; formal scope is an operator/research control, not a software-enforced five-source boundary.

Distinguish the target population of eligible Kenyan digital-news reporting from the **finite available sampling frame**: collected versions passing current L0/L1 gates, carrying a compatible pinned prediction, verified readable evidence and all independence exclusions. Archive availability, collection choices, extraction failures and automated eligibility gates constrain that frame. Scores cannot be generalized to all Kenyan reporting, omitted publishers, all languages, real incidents or population prevalence. L2 evaluation conditional on L0/L1 inclusion is not end-to-end pipeline recall; missed GBV upstream needs separate assessment.

The implemented retrospective collection window is January–August 2026. That is an engineering window, not documentary proof of the formal study period. **TODO SUPERVISOR / RESEARCH DECISION:** approve the actual publication-date window and population statement. Use publication dates, not retrieval/archive dates, for any approved period restriction. The current batch form has no publication-date filter or period stratification. If the approved frame requires either, resolve this gap before execution rather than pretending the UI applied it.

## 3. Validation entry and exclusion rules

A member must meet all of these conditions before independent selection:

1. A current compatible L0 `valid` result and L1 `kenya` result make the version eligible for L2. Review-gated L0 and ambiguous/non-Kenya L1 versions are outside this frame; do not silently force them through.
2. A stored L2 prediction exists for the exact evaluated method/model identity. Weak supervision is not a substitute. Its article/version lineage and probability must be valid.
3. The article is from a formal source and meets the approved publication-period restriction, if any.
4. Normalized content can be retrieved and verified against the pinned version/hash. It is sufficiently readable for semantic assessment; later-discovered evidence problems remain recorded exclusions/unresolved cases, not hidden replacements.
5. It is independent of **all 322 actual training records**, including reviewed negatives, weak labels and the seven weak/unreviewed positive training examples. Label origin does not undo training exposure.
6. It conflicts with neither existing protected membership nor protected historical body hashes.
7. Exact body duplicates are removed within the candidate pool. Near-duplicate and syndication risks are handled under the approved pre-freeze policy.

The training membership provider checks the exact model artifact, training dataset version, model/dataset manifest checksums, record checksum and record count. Missing or inconsistent provenance blocks independent selection. It constructs training article-ID, extraction-version-ID and content-hash sets. Selection also expands training hashes across historical versions of those articles. Thus a newer extraction of the same training article or identical text under another URL is not independent.

Protected batches similarly exclude article IDs, version IDs, stored hashes and historical hashes from candidate selection. A conflicting protected record is rejected regardless of the new batch purpose. For independent purposes, training exposure is rejected too. `diagnostic` permits training-exposed candidates but still excludes protected-reference conflicts. Keep a private exclusion audit; native exclusion counters are sequential reasons, not a complete population flow table, and source/language filter omissions are not separately counted.

### Exact duplicates and near duplicates

Native selection retains one candidate per exact content hash after eligibility/source filtering, with repeatable ordering for a fixed database state. Freeze rechecks training/protected conflicts, membership size, digest, model provenance and pinned article/prediction/hash lineage. Exact hashes do not detect lightly edited syndication, translations, related follow-ups or two articles about one incident.

Proposed policy: screen obvious near-duplicates and syndicated families **before outcomes are reviewed and before membership is frozen**, retain an auditable rule for representatives/groups, and prevent families crossing training and protected reference boundaries. Related reporting is not automatically a duplicate, but dependency limits uncertainty estimates. Never replace a difficult or misclassified member after feedback, or reroll the seed to evade duplicate concerns.

**Implementation gap:** no near-duplicate clustering, syndication-family registry, group-aware sampling or arbitrary candidate-ID exclusion interface is implemented. A private screening log does not change native eligibility. If a known training-related near-duplicate cannot be excluded using the available frame controls, stop and resolve the frame/capability under a separate authorized task. Do not mark it `unable_to_determine` merely to remove an inconvenient outcome, or claim it was excluded by an unused sidecar file. Near-duplicate handling is especially important before final testing.

## 4. Representative and diagnostic sampling

The native purposes are `development_validation`, `final_test` and `diagnostic`; strategies are `random`, `stratified` and `enriched`. `enriched` is permitted only for `diagnostic`.

**Proposed first design: seeded uniform `random` sampling without replacement from the five-source unseen frame.** It does not select on predicted label, score, disagreement or the hoped-for result. If N equals the available frame M, it is a census of that frame, not a larger population. Review frame source/language availability before approving N; plan additional broad, real collection when needed to achieve meaningful coverage. Do not add selected positives after reviewing outcomes and then call the merged sample representative.

Native `stratified` is an alternative requiring explicit approval: proportional allocation across `source|raw_language` strata, integer floor plus largest-remainder allocation, seeded within-stratum sampling and seeded mixing. Small strata may receive zero members; this supplies no minimum English, Swahili, Sheng, mixed-language or publisher support. It is not equal allocation, time stratification or stratification on independently verified language. Finite-sample rounding changes stratum inclusion probabilities. The evaluator is unweighted, so it does not calculate design-weighted population estimates.

For uniform random sampling each candidate's design inclusion probability is N/M. Native configuration stores realized selected/eligible fractions by stratum under `inclusion_probabilities`; for `random` these are **realized allocation fractions, not each candidate's design probability**. For proportional stratification they describe allocated stratum fractions, including zero allocations. Do not infer weighting support from this field.

Diagnostic sampling may enrich likely positives, machine borderline or scores near 0.5 to investigate errors. Native `enriched` shuffles ties with the seed, prioritizes predicted `gbv`/`borderline` over `not_gbv`, then sorts by distance from 0.5. It does not implement calibrated uncertainty, model–weak disagreement selection or discovery of high-confidence mistakes. Those are future diagnostic design options requiring separate authorization. Native evaluator suppresses accuracy/precision/recall/F1 for every `diagnostic` batch, including random diagnostic batches. Report descriptive errors and supports separately; never use diagnostic enrichment as representative accuracy, prevalence or final-test evidence.

## 5. Language representation and verification

Seek meaningful article-level support for English, Swahili, Sheng and English–Swahili/relevant Kenyan code-switching. Taifa Leo should contribute strongly to available Swahili reporting, while article-level verification determines whether it does. Report publisher and language separately, including their overlap; do not rename Taifa Leo results “Swahili performance” or infer Sheng from its inclusion.

Raw normalized `language` metadata is not independently validated. Empty metadata becomes `unknown`; language filters compare literal strings, so `sw`, `Swahili`, mixed tags and legacy template values are not interchangeable. Known legacy Taifa Leo `en-US` template metadata needs review. For the first proposed random frame, leave the language filter empty rather than excluding unknown/mis-tagged articles. Unknown metadata is not evidence of an out-of-scope language.

Proposed research verification: a competent reviewer identifies article language, meaningful code-switching and uncertainty separately from GBV, with consistent conventions and a private pinned-version record. Ideally verify the frame before a reviewed-language stratified design. Where that is not possible, use raw-language random sampling and describe language verification after selection as subgroup characterization, not the original sampling variable. Do not filter out inconvenient cases post-selection.

**Implementation gap:** there is no reviewed-language registry, language override for batch strata, competence roster or built-in subgroup report. A private approved language sidecar can support later auditable analysis but does not alter native strata. Its linkage and handling of mixed/unknown languages require approval. If verified language quotas are required, the current workflow cannot enforce them. Where Sheng or any subgroup is too small, report support and privacy-safe descriptive error patterns; do not fabricate stable subgroup metrics or statistical reliability. Bilingual/Sheng review and translation limits must be agreed before first review.

## 6. Sample-size and precision planning

**N is not yet approved.** The UI's default 20 and accepted range 1–10,000 are engineering values, not sample-size justification. Software refuses N larger than the unseen eligible frame; it does not supplement the sample or waive exclusions. The recorded at-most-two upper bound cannot support a meaningful multilingual model assessment.

Preregister the following before inspecting validation outcomes:

- Actual unseen eligible frame size M, source/verified-language coverage and period.
- Expected human-positive fraction, with provenance from a separate pilot/planning assumption; neither training 10/322 nor model 11/324 is a validated population prevalence estimate.
- Desired **human-positive binary support** for recall, predicted-positive binary support for precision, total support, confidence level and interval precision.
- Minimum reportable publisher/language support, expected semantic uncertainty/model abstention, reviewer competence, review/adjudication burden and available budget.
- N, any finite-population/design/dependency adjustment, maximum collection/review budget and a prespecified stop rule independent of favorable scores.

For orientation only, a large-sample binomial approximation for a desired recall interval half-width h is `n_positive ≈ z² × r × (1 − r) / h²`, where r is an assumed recall and z the chosen confidence quantile. This is planning arithmetic, **not an observed result or an approved N**. Total sample planning must account for expected human-positive prevalence and the probability that a positive receives a resolved binary reference and a non-abstaining prediction. Model abstention correlated with positives makes naive inflation unreliable. Similar denominator planning is needed for precision. Sparse supports require an appropriate interval method rather than a confident normal approximation; [NIST's discussion of binomial proportion intervals](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm) provides methodological context.

**TODO SUPERVISOR DECISION:** approve N, positive support, precision targets, confidence intervals and collection budget/stop rule. A confidence-interval method must reflect the design and any article-family dependence; the native evaluator computes no intervals. If the agreed support cannot be achieved, report the limitation or use a separately versioned new frame/cohort under a prespecified design. Do not keep sampling until F1 looks acceptable or a chosen number of discovered positives is reached and then apply ordinary fixed-N inference without accounting for that stopping rule.

Zero human-positive or predicted-positive denominators make the corresponding metrics undefined; native output is NULL, not zero or perfect performance. A sample with no positives can describe observed negatives, not validate GBV recall. Collect additional real support under a separate approved design rather than silently merging diagnostic positives into the representative batch.

## 7. Proposed first configuration and reproducibility record

| Setting | Proposed value / constraint |
| --- | --- |
| Name | `L2-VALIDATION-V1` |
| Layer / purpose | `L2` / `development_validation` |
| Strategy | `random`, representative of the specified eligible frame |
| Protection | Enabled before freeze; retain thereafter |
| Model version | `l2-afroxlmr-dev-v1` |
| Method name | `afroxlmr_gbv_relevance` |
| Exact method version | `l2-47035d92f81cd5240062610d` |
| Pretrained family / revision | `Davlan/afro-xlmr-base` / `25f27299c247a6b73a767bd82d12444138b19337` |
| Decision configuration | Existing positive ≥0.8, negative ≤0.2, middle band `borderline`; **unvalidated engineering thresholds** |
| Codebook | Researcher-finalized L2 GBV Relevance Codebook v1.0; identifier `l2-gbv-relevance-codebook-v1.0`; runtime configuration/content pinning still to be verified |
| Formal source filter | `nation,standard,star,citizen,taifaleo` |
| Language filter | Empty for initial random selection; preserve unknown/unvalidated metadata and verify article languages separately |
| N | **TODO SUPERVISOR DECISION**, subject to available independent M |
| Seed | **42 proposed**, derived from the existing UI default and adopted here as a research proposal pending approval |
| Membership | Immutable after freeze; exact prediction and extraction pointers retained |

Seed 42 is for reproducibility, not methodological superiority or independence. Sampling sorts candidates by annotation identifier before seeded operations. The same seed/configuration reproduces selection only with the same candidate frame and ordering, compatible runtime/implementation and verified artifacts. Do not retry different seeds to improve outcomes or subgroup appearance. Freeze and archive the frame as well as the selected members.

| Native record | Stored evidence |
| --- | --- |
| Batch | Name/ID, layer, purpose, model/method identities, guideline string, strategy, seed, requested size, protection, lifecycle status and creation/freeze/completion timestamps |
| Batch configuration | Source/language filters; unvalidated-language flag; eligible pool size; sequential exclusions; training dataset version, manifest hash and record count; model manifest hash; membership digest; selection policy; stratum allocation fractions; near-duplicate limitation |
| Member | Article/version/prediction pointers, content hash, source, raw language, stratum, selection reason/order, status, immutable first-review pointer and accepted final-review pointer |
| Human review | Exact machine/article/version lineage, configured reviewer identity, guideline version, semantic label or NULL, workflow decision, reason, timestamp and superseded-review link |
| Private evaluator export | Initial/final reference pointers, pinned model label/probability, final human label/decision, identities, order/stratum and deterministic output hashes |

Actual IDs, reference records, article bodies, pair exports and detailed rationales remain private under the established storage/data policy. Public docs must not contain them. Existing selection reasons call both random and stratified membership `representative_random_selection`; use the batch strategy/configuration to distinguish the design.

Proposed private governance archive: approval/owner/effective date; codebook and protocol checksums; code commit and runtime; approved publication window; full eligible frame snapshot and digest; verified-language/competence record; duplicate-screening policy; sample-size justification; reviewer exposure declarations; acceptance criteria; deviations and revision/adjudication evidence. **Implementation gap:** the app stores selected membership/configuration, not the full eligible frame, document contents/signatures or these research approvals. Establish an auditable approved archive procedure before execution; a selected-membership digest alone cannot reconstruct a changing pool.

## 8. Freeze, blinded review and adjudication

### Lifecycle and native enforcement

`draft → frozen → in_review → completed` is the native sequence. Preview/create pins a sampled draft. Freeze rechecks verified training/model manifests, conflicts, count, digest and article/prediction/hash lineage, then activates protected membership. Membership cannot be resampled after freeze. The first successful decision sets the immutable initial human-review pointer; later permitted append-only decisions can update the final pointer during `in_review`. Completion locks the accepted final pointers. A new model prediction does not replace the pinned prediction being reviewed or evaluated.

Reviews require the configured guideline string to match the frozen batch and use the existing local token/CSRF workflow. New resolved labels require verified article text; unresolved submissions remain possible when it is unavailable. Concurrent/stale submissions conflict rather than silently replacing a saved batch decision. Completed accepted references cannot be revised through the batch workflow. Later general annotation reviews do not change completed batch pointers.

### Actual blinding and its limits

Before a member's first saved decision, the batch review template hides the machine label, probability and evidence; choices are initially blank and a reason is required. Review the full verified pinned text and codebook first. The interface does not show a default machine answer. After saving, development/diagnostic members can reveal the pinned label/probability comparison. **Final-test batch review keeps that comparison hidden after save too.**

The proposed initial reviewer package excludes model thresholds, weak labels, agreement/disagreement, evaluation metrics and aggregate outcomes that could anchor judgment. The batch form does not display those machine answers or thresholds, but the operator-facing protocol/configuration and ordinary result pages can reveal them. Provide the approved semantic codebook and necessary article provenance to the reviewer; do not claim technical isolation of this package where it is absent.

The workspace still permits ordinary automated-results/review pages, and batch progress exposes aggregate human-label counts. Reviewer memory and earlier weak-layer review are not erased. Thus initial-form blinding is implemented, but isolated reviewer roles and complete aggregate/answer blinding are not. Proposed conduct: use a qualified reviewer without prior member-level exposure where feasible; avoid other result pages and aggregate labels before completing independent review; declare exposure and preserve it in the private record. No interface claim can substitute for that declaration.

### Accepted reference after feedback

The evaluator scores the **final accepted pointer**, not automatically the first blind decision. The current app allows revisions after development feedback before completion. Preserve first decisions and do not revise merely to align with model output. Proposed baseline policy is that resolved first blind decisions remain the accepted references unless an independently justified correction/adjudication is authorized and documented. Model feedback is not adjudication evidence.

**TODO SUPERVISOR DECISION:** approve first-versus-final reference acceptance and treatment of feedback-exposed revisions before any review. **Implementation gap:** no automatic initial-versus-final metric comparison, revision-contamination audit or enforcement of this proposed baseline policy exists. Native pairs retain both pointer IDs but score only final labels. If approved acceptance requires scores against initial blind labels, or independently adjudicated references unsupported by the current workflow, resolve the capability gap under separate authorization before evaluation; do not present final-feedback labels as unqualified blind ground truth.

### Second reviewers and unresolved cases

A feasible proposal for the current local workspace is a qualified initial reviewer with logged unresolved cases; whether this is sufficient research evidence is pending approval. Decide whether all records or a prespecified subset require independent second review, the subset rule/proportion, an adjudicator, competence/conflict criteria and accepted-reference rules. Do not select second-review coverage only after seeing favorable model agreement. Any disagreement analysis must use genuinely independent paired decisions.

Native `unable_to_determine` and `needs_adjudication` store NULL human labels; `confirmed`/`corrected` can store any of the three L2 semantic labels. An append-only revision can resolve a referral, but it is not a built-in adjudication process. **Implementation gap:** no A/B assignment, independent duplicate annotation, adjudicator permissions, agreement statistic or separate adjudication record is implemented. A configured reviewer identity alone does not establish independence. If double annotation is mandatory for acceptance, do not execute an unsupported substitute and call it complete.

## 9. Metric eligibility, reporting and thresholds

| Accepted human outcome | Pinned model outcome | Native treatment |
| --- | --- | --- |
| Resolved `gbv` or `not_gbv` | `gbv` or `not_gbv` | Included in binary confusion matrix |
| Resolved `gbv` or `not_gbv` | `borderline` | Model abstention; excluded from binary metrics |
| Resolved semantic `borderline` | Any | Human uncertainty; excluded from binary metrics, but counted as workflow-resolved |
| `unable_to_determine`, NULL | Any | Unresolved; excluded from binary metrics |
| `needs_adjudication`, NULL | Any | Unresolved referral; excluded from binary metrics |
| Missing accepted review or invalid lineage/digest/probability | Any | Evaluator refuses the batch rather than silently omitting it |

With positive class `gbv`, TP is human-positive/model-positive; FN human-positive/model-negative; FP human-negative/model-positive; TN human-negative/model-negative. Binary support is `n = TP + FN + FP + TN`. Native calculations are:

- Positive precision: `TP / (TP + FP)`.
- Positive recall: `TP / (TP + FN)`.
- Positive F1: `2TP / (2TP + FP + FN)`.
- Conditional binary accuracy: `(TP + TN) / n`.
- Model abstention rate: number of model `borderline` members divided by all batch members.

Zero denominators produce NULL. These scores are conditional on **both** an accepted binary human reference and a non-abstaining model. Human-positive/model-borderline cases are excluded from FN by the evaluator; consequently conditional recall does not measure the model's full ability to return a positive on every human-positive article. Separately report positive-reference abstentions and coverage, and prespecify any application-level abstention-cost analysis. Do not silently convert human or machine borderline, inability or adjudication into negative truth.

Report total sampled/reviewed members, source/raw and verified-language support, human label/decision counts, unresolved counts, binary support, excluded count, model label counts, confusion matrix and abstention rate alongside any score. Exclusion count is the union of ineligible binary pairs; uncertainty and abstention can overlap, so do not add their totals as if disjoint. Native `resolved` includes semantic borderline, while `reviewed` includes unresolved decisions; neither establishes adequate binary support or passed adjudication.

Native report includes configuration/provenance, those counts and GBV precision/recall/F1/accuracy. NULL unresolved workflow counts appear in the human-label counter under decision names when present; progress distinguishes inability from adjudication. The report includes NULL placeholders for ROC-AUC, PR-AUC and calibration. It does not calculate negative-class precision/recall/F1, macro-F1, design weights, intervals, publisher/language metrics, positive-specific abstention rates or adjudication agreement. **Implementation gap:** these additional analyses need an approved, audited private analysis procedure or later separately authorized implementation. Do not imply they are already native outputs or fabricate values. With insufficient subgroup support, descriptive findings and an explicit limitation are preferable to unsupported comparisons.

The private CLI accepts only completed batches and rechecks membership size/digest, pinned model lineage, finite probability and accepted-review article/version/guideline lineage. Outputs are private pairs/report plus deterministic hashes under ignored `data/`, never public raw reference data. `diagnostic` suppresses representative metrics. For `final_test`, `--final-experiment` is required to release evaluation; the flag is an operator assertion, not an approval service or enforced one-shot experiment.

Keep current **0.8/0.2 unvalidated engineering thresholds** fixed for the first honest development assessment. No calibration claim follows from training loss or prediction counts. Later threshold selection may use approved development-validation evidence only, with separate versioned configuration/method identity and clear reuse disclosure. Never use final-test labels/results for threshold tuning, training, active learning or model selection. Freeze model, preprocessing, tokenizer, thresholds, codebook and analysis plan before a separately designed final test. Record and honor a single approved final experiment; the software does not enforce one-time CLI execution.

**TODO SUPERVISOR DECISION:** preregister numeric model acceptance thresholds, minimum supports, uncertainty handling and language/publisher criteria. Batch completion is not model acceptance, and selecting thresholds after observing a final-test score invalidates its claimed independence.

## 10. Training protection and leakage-prevention checklist

Frozen protected batches are consulted by reviewed-only, mixed-effective and weak-bootstrap dataset exports and private review-priority selection. Exclusion includes article/version IDs and exact/historical hashes; existing manual reference manifests remain supported. The training CLI rechecks even an older export against current protected membership before loading the model. Missing validation schema fails closed on these protected export/training paths. Protection does not require deleting existing model or human history.

Avoid concurrent batch freezing and training: a pre-load check does not prove exclusion from an already running job. Direct low-level training functions do not consult the database. Future experiments must preserve complete training provenance and demonstrate exclusion again. A protected reference cannot be silently recycled into training simply because it was useful for development analysis. Final-test active-learning/tuning restrictions are research controls, not a full role-separated software authorization system.

Complete this checklist for a later authorized batch; boxes here remain unchecked because no batch was created:

- [ ] No dev-v1 training article IDs in independent validation.
- [ ] No dev-v1 training version IDs in independent validation.
- [ ] No dev-v1 training body hashes in independent validation.
- [ ] Historical training and protected hashes checked.
- [ ] Protected reference members excluded from later training.
- [ ] Validation membership frozen.
- [ ] Final-test membership not used for active learning.
- [ ] Final-test labels not used for threshold tuning.
- [ ] Final-test results not used for model selection.
- [ ] Exact duplicates prevented across protected boundaries.
- [ ] Near-duplicate/syndication risk documented and handled under the approved policy.
- [ ] Five-publisher formal scope respected; engineering-only sources separated.
- [ ] Language and publisher not conflated; language evidence/uncertainty recorded.
- [ ] Researcher-finalized codebook version and exact content checksum archived/pinned; required external approvals recorded.
- [ ] Exact model identity and artifact provenance pinned.
- [ ] Exact prediction identity pinned.
- [ ] Sampling configuration, eligible frame and seed stored privately.

## 11. Completion, analysis readiness and later work

Native completion requires `in_review` and an initial decision for every member, then locks final accepted pointers. It **permits unresolved and semantic-borderline records**; it does not automatically adjudicate them or enforce positive support, bilingual coverage or research acceptance. Do not replace or fabricate those decisions to complete a batch.

For research analysis readiness require frozen intact membership; full intended review coverage; accepted-reference/revision and unresolved handling under the approved policy; preserved model/prediction/codebook/configuration; ongoing training protection; all deviations documented; and successful evaluator integrity checks. The evaluator requires software status `completed`, so the order is: confirm policy and review coverage, lock accepted pointers, then perform private integrity-checked evaluation under separate authorization. Only then designate the batch analysis-ready. If integrity checks fail, stop and investigate; completion alone does not certify readiness or pass the L2 research gate.

The following is a **future gated sequence**, not authorization to execute it in this documentation task:

1. Pin the finalized codebook; agree the sampling protocol and required approvals,
   confirm sufficient unseen real support and resolve required gaps; separately
   authorize the actual development batch.
2. After review/completion, run the private evaluator and examine confusion counts, false positives, false negatives, excluded human uncertainty and machine abstentions.
3. Examine publisher differences and independently verified language differences only where support permits; identify missing positive patterns without exposing sensitive text.
4. Collect additional real development articles under an approved plan; human-review additional development examples while keeping protected references excluded.
5. Create a new traceable development dataset and, under separate authorization, train `l2-afroxlmr-dev-v2`.
6. Compare dev-v1/dev-v2 under an approved development-validation strategy, preserving exact pinned predictions and comparable frame/membership. Do not relabel a frozen reference or overwrite dev-v1 outputs.
7. If approved, calibrate thresholds using development evidence only; document selection/reuse and freeze the chosen model/configuration.
8. Design and freeze a separate independent final-test set with approved sample size, language/publisher support, duplicate protections and analysis plan.
9. Run the final test once under the locked experiment, then report performance and limitations without feedback-driven model selection.

Repeated development-validation feedback is useful for development but cannot become an untouched final test. No real `L2-VALIDATION-V1`, later model or final test is created by these documents.

## 12. Implementation cross-check and gaps

This is a source-code audit, not a new live schema installation, model run or validation result.

| Area | Current implementation | Research control or gap |
| --- | --- | --- |
| Purposes / strategies / size | Three purposes; three strategies; enriched diagnostic-only; N 1–10,000 and no larger than eligible M | Approve N/design; UI defaults do not supply research justification |
| Source/language filters | Seven supported source keys; exact raw-language matching; explicit unvalidated flag | **Implementation gap:** formal-five enforcement, reviewed-language quotas/registry and publication-date filtering/stratification absent |
| Sampling reproducibility | Stable annotation-ID sorting, local seeded random generator, proportional largest-remainder strata, selected digest | **Implementation gap:** full eligible frame archive absent; stored random stratum fractions are not design probabilities |
| Training/protection | Checksummed exact training membership, historical hashes, protected conflicts, exact pool dedup, freeze recheck | **Implementation gap:** near-duplicate/syndication and group-aware exclusion absent |
| Lifecycle / pointers | Draft/frozen/in_review/completed; guarded frozen membership, immutable initial pointer, completed final pointer | **Implementation gap:** no automatic initial/final contamination comparison or approval of accepted-reference policy |
| Blinding / reveal | First-answer label/probability/evidence hidden; development comparison after save; final-test comparison sealed | **Implementation gap:** ordinary results remain accessible, human aggregates visible, prior exposure persists; no isolated reviewer roles |
| Labels / unresolved / completion | Three semantic labels; four review decisions; unresolved labels NULL; completed batch may contain unresolved records | Research policy must decide acceptance, support and permitted unresolved fraction |
| Adjudication | Referral flag and append-only revision only | **Implementation gap:** independent A/B review, adjudicator roles/records and agreement analysis absent |
| Evaluation | Final accepted binary pairs; explicit abstention exclusion; unweighted metrics; integrity checks | **Implementation gap:** initial-blind scoring, subgroup/interval/weighted analyses and positive-specific abstention report absent |
| Codebook governance | Frozen guideline string and lineage check | **Implementation gap:** approved content/signature/checksum, protocol archive and competence evidence not native |
| Future training / final release | Protected exports/priority, CLI older-export recheck; final-test explicit evaluation flag | **Implementation gap:** low-level training bypass, concurrent-job boundary and final one-shot/reviewer isolation require operator governance |
| Schema / RLS / readiness | PostgreSQL checks table presence, named check/unique constraints, enabled guard triggers with matching function names, content index and RLS enabled; guarded migration preserves immutable lineage | **Implementation gap:** readiness is not a full audit of SQL definitions, RLS policies, role grants or approval authority. Verify intended target independently. SQLite offline tests do not prove PostgreSQL enforcement. |

The migration enables RLS on the new tables; this does not imply a public review API, authenticated multi-user roles or completed ethics approval. The documented development installation passed rollback-only guard checks on 6 October; that historical evidence is not a fresh readiness check for every target. No migration, policy, code, test behavior or database state changes in this documentation task.

## Change Log

| Version | Date | Change | Approval |
| --- | --- | --- | --- |
| 1.0 | 7 October 2026 | Initial development-validation design; formal five-source scope; training/exact-duplicate exclusions; multilingual and sample-size planning; audited workflow limits and pending approvals. | Pending |
| 1.0 | 7 October 2026 | Recorded companion codebook finalization and current roadmap synchronization; sampling design/acceptance and real batch execution remain pending. | Protocol approval not asserted |

## Decisions Requiring Supervisor Approval

- **TODO SUPERVISOR / RESEARCH DECISION — documentary population alignment:** reconcile approved proposal/ethics amendments, Citizen TV/Citizen Digital mapping and publication window. Formal five-source scope is specified; any later expansion requires a documented amendment.
- **TODO SUPERVISOR DECISION — design and support:** approve random versus native raw-language proportional stratification, N, minimum human-positive/predicted-positive and subgroup support, precision/interval targets, collection budget and stop rule.
- **Semantic standard finalized; protocol decision pending:** use companion codebook v1.0 for substantive/incidental, genre and uncertainty rules. Agree admissible unresolved proportions, review acceptance and uncertainty reporting for this sampling design; separate supervisor approval is not asserted.
- **TODO SUPERVISOR DECISION — language evidence:** approve article-level language/mixed conventions, bilingual/Sheng competence, metadata verification timing, sidecar audit procedure and subgroup reporting thresholds.
- **TODO SUPERVISOR DECISION — independence and duplicates:** approve pre-freeze syndication/near-duplicate handling and family/dependency policy, especially for final testing; resolve unsupported exclusions before execution.
- **TODO SUPERVISOR DECISION — review acceptance:** approve first-blind versus final-reference scoring, feedback-exposed revision handling, second-review requirement/proportion/subset rule, adjudicator and accepted-reference procedure. Required unsupported capabilities must be resolved first.
- **TODO SUPERVISOR DECISION — performance acceptance:** preregister numeric acceptance criteria, treatment/cost of abstentions, minimum evidence and whether the available conditional metrics meet the research objective; supplementary engineering metrics must remain separate from formal five-source claims.
- **TODO SUPERVISOR DECISION — later calibration/final test:** approve when development-validation reuse can guide thresholds, later model comparison, separate final-test sampling/design, frozen experiment and one-time reporting policy.
- **TODO SUPERVISOR / RESEARCH DECISION — authorization and archive:** name the owner, record approval/effective date and versioned content/eligible-frame archive, and resolve blocking implementation gaps before a separately authorized real batch.
