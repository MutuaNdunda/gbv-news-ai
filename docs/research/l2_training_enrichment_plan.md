# L2 training enrichment and next development cycle

Updated **16 October 2026 (EAT)**. This records the researcher's documentation
request and the proposed next experiment. It does not execute collection,
annotation, retraining, threshold changes or final testing, approve a sampling
protocol, or close a research gate.

## Completed baseline and next stage

`L2-VALIDATION-V1` completed on 13 October 2026 at 16:19:19 EAT; its first private
development evaluation was generated at 16:22:39 EAT. Preserve its sealed membership,
accepted pointers and original report. The model remains `l2-afroxlmr-dev-v1`,
method `l2-47035d92f81cd5240062610d`, with original 0.80/0.20 thresholds.
This is development validation, not the untouched final thesis test.

Next: privately interpret the existing report; agree reference-quality follow-up;
resolve upstream extraction, eligibility and sampling gaps; strengthen reviewed
training support; then agree a new versioned baseline/Transformer experiment.
The 381 title-only decisions among 400 accepted workflow decisions, instrument
reconciliation, publisher scope, unverified language/date metadata and related-story
risks still limit interpretation. Any reference-quality follow-up needs a separate
versioned design; do not reopen or relabel the completed batch.

## Positive support and class balance

The original model trained on **322 mixed-effective binary records: 10 GBV and
312 not-GBV (about 3.1% GBV)**. Only three positives were human-reviewed. Existing
class weighting does not create new examples or resolve limited positive diversity.

There is no universally correct training percentage. A **proposed initial experiment**
is several hundred distinct, body-reviewed GBV examples and approximately
**30–50% GBV in the binary training subset**. An illustrative dataset is
300 GBV plus 700 not-GBV articles (30% positives). These are planning suggestions,
not approved quotas, minimum scientific adequacy thresholds, observed new counts,
or guarantees of performance. The example is a development subset, not a replacement
for the proposal's minimum 5,000-article annotated corpus target.

Compare feasible compositions on separate development data and use learning curves,
per-class precision/recall/F1, coverage/abstention and subgroup support to assess
whether more examples help. Record class weighting/resampling and seeds; balance
experiments must not repeatedly inspect the final test. Do not discard useful
negatives solely to achieve a ratio or count duplicated/oversampled rows as new
independent positive evidence.

Coverage should include GBV forms, ordinary negatives, difficult keyword-matching
negatives, indirect GBV descriptions, publishers, publication periods and verified
article languages. Report sparse groups honestly; publisher identity cannot verify
language. Semantic borderline and unable-to-determine cases remain separate from
binary labels under the finalized codebook.

## Broad collection plus targeted training enrichment

Keep broad non-keyword collection as the corpus foundation. Supplement it with
separately identified GBV-term runs to find additional training candidates. A match
is a discovery signal, never a human-confirmed GBV label or ground truth.

1. Define the study publishers/publication window, collection budget, stop rule,
   term-list version and intended training/diagnostic use before running.
2. Use varied English/Swahili terms and phrases with competent language review;
   search broad reporting too, because implicit descriptions and other language
   forms may omit those terms. Do not infer Sheng coverage from a keyword list.
3. Use existing bounded Wayback discovery and publisher parsers. Current term
   filtering is **literal, case-insensitive OR matching on URLs**, not article-body
   or headline search. URL slugs and bounded archive coverage can miss relevant news.
4. Preserve run configuration, terms, selection/bounds, original/canonical URLs,
   publisher, publication/capture dates, parser versions and content hashes.
   The current collector records `discovery_terms` and
   `candidate_sampling=url_keyword_enrichment` on targeted article records.
   Keep the versioned term list and design record privately with run evidence;
   automatic term-list-version or incident-family management is not implemented.
5. Apply the existing L0-valid → L1-Kenya gates. Review readable, verified article
   bodies against the codebook before accepting training labels. Keep useful
   non-GBV matches and broad-source negatives; record evidence basis and uncertainty.
6. Resolve exact duplicates and related/syndicated/incident families before splitting.
   Preserve every protected reference article/version/hash exclusion and extend the
   design to related families; native exact-hash exclusion alone is insufficient.

See [README collector commands](../../README.md#shared-historical-wayback-and-keyword-discovery)
and [collection protocol](../collection_protocol.md). Verify intended-target schema,
including collection-run control, before updated workers run; dated installation
observations are not a fresh readiness check. Respect existing publisher restrictions.

## Training, development and final-test separation

| Cohort | Selection and permitted use |
| --- | --- |
| Training | Broad candidates plus documented targeted enrichment; accepted human labels and explicit weak-label provenance where used; no protected reference members or related families. |
| Development | Separately held-out data for model selection, class-balance experiments and threshold/calibration exploration. Report any enrichment and selection bias. |
| Existing v1 batch | Protected development-validation evidence. Preserve sealed decisions and original model/report; exclude from training. Feedback exposure prevents treating it as a new untouched final test. |
| Final test | A separately agreed, frozen human-reviewed sample representing the intended news stream, with sufficient class/subgroup support and family separation. Keep untouched during development. |
| Targeted diagnostic assessment | Separately report enrichment and limits. Unweighted results do not establish representative news-stream performance or GBV prevalence. |

A representative final sample need not have an artificially balanced label mix.
Any disproportionate stratification requires prespecified design-aware analysis;
do not assume the current evaluator implements sampling weights. Keep threshold
exploration on development data and freeze the model/configuration before final testing.
Selective evaluation sampling can bias ordinary risk estimates; see the primary
research paper [Active Testing: Sample-Efficient Model Evaluation](https://proceedings.mlr.press/v139/kossen21a.html).

## Reproducible handoff before a new model

Record dataset membership/version, source and verified-language support, class and
evidence counts, duplicate-family/split rules, protected exclusions, codebook version,
code commit, seed, weighting, model/tokenizer/preprocessing identity and evaluation
plan. Compare simple TF-IDF baselines with the new Transformer when separately
executed. Preserve dev-v1 and all historical predictions as immutable evidence.
Scores, article text, review identities and individual labels remain in ignored
private storage; public Markdown may record methods and aggregate operational status.

L3 types, L4 NER/geocoding, L5 safety and the final analytical dashboard remain
separately gated. The public Sheet controls sequencing; this proposed enrichment
plan does not amend its canonical rows or claim supervisor/protocol approval.
