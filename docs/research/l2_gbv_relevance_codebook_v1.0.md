# L2 GBV Relevance Codebook v1.0

| Metadata | Value |
| --- | --- |
| Version | 1.0 |
| Status | **Finalized by the researcher — 7 October 2026** |
| Research layer | L2 — GBV Relevance |
| Applicable development model | `l2-afroxlmr-dev-v1` |
| Unit of analysis | Eligible digital-news article, represented by its pinned extraction version |
| Formal publishers | Daily Nation; The Standard; The Star; Citizen TV; Taifa Leo |
| Languages | English; Swahili; Sheng; English–Swahili and other evidenced Kenyan code-switching |
| Owner | Project researcher; named document owner to be recorded in the approval record |
| Finalization authority | Researcher's explicit confirmation in this session; no separate supervisor or ethics approval is asserted |
| Draft prepared | 7 October 2026 |
| Researcher finalization date | **7 October 2026** |
| Guideline identifier | `l2-gbv-relevance-codebook-v1.0` |
| Operator guide | [Create the first independent L2 validation dataset](validation_dataset_creation.md) — operational support; no semantic-rule change |
| Companion document | [L2 Validation Sampling Protocol v1.0](l2_validation_sampling_protocol_v1.0.md) |

## 1. Authority, scope and limits

This document is the researcher-finalized human semantic standard for L2 v1.0, as explicitly confirmed on 7 October 2026. It does not retrospectively certify existing weak labels, human corrections or model predictions. Read [the annotation implementation](../annotations.md) for executable behavior and [the engineering log](../roadmap/IMPLEMENTATION_STATUS.md) for dated evidence. The companion sampling protocol, batch design and independent evaluation remain separate unfinished work. Finalization does not establish a supervisor signature, ethics amendment, archived checksum or configured runtime guideline identity.

The repository describes a postgraduate, ethical, human-supervised multilingual GBV news study. The five-publisher formal scope below follows the researcher's explicit updated instruction. No signed proposal, supervisor approval or formal amendment establishing every operational detail was located in the inspected repository. Repository summaries are evidence of project intent, not documentary proof of research or ethics approval. **TODO SUPERVISOR / RESEARCH DECISION:** reconcile the approved proposal and any required amendment with this codebook, including the Citizen TV/Citizen Digital operational mapping and study dates.

| Formal study publisher | Existing software source key | Interpretation |
| --- | --- | --- |
| Daily Nation | `nation` | Digital article corpus |
| The Standard | `standard` | Digital article corpus |
| The Star | `star` | Software/documentation also calls this The Star Kenya |
| Citizen TV | `citizen` | Existing collector targets Citizen Digital; confirm that these digital articles represent the approved Citizen TV population. It does not collect television transcripts. |
| Taifa Leo | `taifaleo` | Important intended contribution to Swahili representation; verify each article's language |

Tuko (`tuko`) and Kenyans.co.ke (`kenyans`) remain **engineering, development or diagnostic sources only** unless a formal scope amendment is evidenced. The seven-source engineering corpus does not itself define the five-source thesis population. Keep formal and supplementary diagnostic results separate.

Publisher and article language are separate variables. A Taifa Leo article is not automatically Swahili, and Taifa Leo does not automatically establish Sheng coverage. The formal language targets require readable article-level evidence and competent review. Availability of a publisher or a multilingual encoder does not prove multilingual validity.

## 2. Research question and unit of analysis

**Does this eligible Kenyan digital-news article report or substantively discuss gender-based violence under the study definition?**

A `gbv` label means the article contains substantive reporting or discussion meeting this definition. It does not establish the truth of an allegation, guilt, a confirmed incident, a police determination or a judicial finding. A `not_gbv` label means the article does not meet the relevance definition; it does not establish that no violence occurred in the real world.

Count articles, not incidents or victims. One article can discuss several incidents; several articles can discuss the same incident. L2 does not establish prevalence, identify incident locations, assign L3 violence subtypes or make legal determinations. L0 readability/provenance and L1 Kenya relevance remain separate prerequisites; source identity cannot replace those checks.

## 3. Semantic labels and review decisions

| Semantic label | Operational definition | Reference treatment under v1.0 |
| --- | --- | --- |
| `gbv` | Sufficient readable article evidence substantively reports or discusses qualifying violence, abuse, coercion or harmful conduct with supported GBV context. | Binary positive when the final accepted review has a resolved decision. |
| `not_gbv` | Sufficient readable article evidence fails the substantive GBV relevance rule. Generic crime, a woman's involvement or isolated terminology alone is insufficient. | Binary negative when the final accepted review has a resolved decision. |
| `borderline` | The readable article supplies enough context to assess relevance, but genuine semantic ambiguity or conflicting evidence prevents a defensible binary decision. | Retain as semantic uncertainty; exclude from binary metrics and report its support. |

| Workflow decision | Meaning in the existing review contract |
| --- | --- |
| `confirmed` | Submitted human semantic label matches the pinned machine label; this records agreement, not objective truth. |
| `corrected` | Submitted human semantic label differs from the pinned machine label; preserve both outputs. |
| `unable_to_determine` | Evidence or reviewer competence is insufficient: missing/corrupt body, inaccessible verified text, crucial omitted context, or language beyond the reviewer's competence. **Human label must be NULL.** |
| `needs_adjudication` | An unresolved case is referred for a further qualified decision under the approved policy. **Human label must be NULL** under the current contract. |

`borderline` is a semantic judgment; `unable_to_determine` and `needs_adjudication` are unresolved workflow decisions. Do not substitute one for another. A model's middle probability band does not establish human ambiguity. A missing body is not semantic `borderline`. The interface cannot store both a substantive provisional label and `needs_adjudication` in one review. A confirmed human `borderline` is workflow-resolved but remains ineligible for binary scoring.

In the validation workspace, reviewers choose the semantic label or unresolved decision first. Software derives `confirmed`/`corrected` only after submission. It therefore does not require reviewers to see or agree with a machine answer. Reasons are required for every batch decision. Reviews are append-only; corrections do not overwrite machine predictions or earlier human decisions.

## 4. Inclusion rules

The conceptual definition concerns harmful acts connected to gender, gendered power or coercion, including physical, sexual and psychological harm, threats and restrictions of liberty. Gender-based violence can affect people of different sexes and gender identities; women and girls are disproportionately affected. This orientation follows [UNFPA's human-rights standards on GBV](https://www.unfpa.org/universal-sexual-reproductive-health-rights-calculator/human-rights-standards-on-gender-based-violence). It is not an assertion that every category in that source is adopted by this study.

Include substantive reporting or discussion of the following **L2 v1.0 relevance domains**. These examples do not define a finalized downstream subtype taxonomy:

- Rape, attempted rape, sexual assault, sexual exploitation, sexual coercion and sexual violence involving children. Legal outcome and survivor sex are not prerequisites for relevance.
- Intimate-partner violence and domestic abuse where abuse, coercion, threats or harm are supported. Ordinary family disagreements are insufficient. Partner abuse can include physical aggression, sexual coercion, psychological abuse and controlling behavior, consistent with [WHO's description](https://www.who.int/health-topics/violence-against-women/).
- Female genital mutilation and related coercion or harm.
- Coercive control, psychological/emotional abuse and economic abuse where the article supports abusive control and gendered or intimate-partner context; ordinary financial disagreement is insufficient.
- Technology-facilitated GBV, such as sexual blackmail or non-consensual intimate-image distribution. Ordinary online disagreement is insufficient.
- Gender-related killing/femicide where context supports that interpretation. A female homicide victim alone does not establish femicide or GBV.
- Other violence, exploitation or harmful practices only where the article supports the qualifying GBV mechanism. Sex, age, occupation, marriage or kinship alone cannot supply the missing mechanism.

Men, boys and people with diverse gender identities must not be excluded merely because they are not women or girls. Conversely, violence involving a woman or girl must not be included solely because of her sex. Researcher finalization adopts these substantive boundaries for v1.0; documentary reconciliation with the approved proposal remains separate.

An article can meet L2 through incident reporting **or substantive discussion** of prevention, survivor support, justice, advocacy, policy or research. It need not narrate a new incident. The substantive rule below applies equally to each genre.

## 5. Exclusion rules

Assign `not_gbv` when sufficient article evidence shows no substantive qualifying GBV relevance, including:

- Generic robbery, theft, assault or homicide without supported sexual, intimate-partner, gendered abuse or other qualifying GBV context.
- Political violence, traffic accidents, sport, routine property disputes, ordinary family conflict or general court reporting without that context.
- Metaphorical “violence,” isolated keywords, quoted/negated language unrelated to a substantive GBV discussion, or a headline contradicted by a clearly non-GBV body.
- General gender policy, representation, employment or health reporting without substantive violence/abuse content.
- A passing reference to a historic GBV case in an otherwise unrelated story, where removing it does not change the story's central topic.

Absence of particular English or Swahili keywords is not an exclusion rule. Reporting may describe abuse indirectly or through local idioms. A readable article with genuinely unclear qualifying context may be `borderline`; an incomplete article with crucial context absent is `unable_to_determine`.

## 6. Operational substantiveness and incidental mentions

The v1.0 test has two parts:

1. GBV is a principal topic **or** a central issue without which the article's main event or argument cannot be understood.
2. The article provides meaningful description or discussion of the conduct, its mechanism, harm, legal/policy response, prevention or survivor support.

Both parts must be satisfied. Record a brief rationale identifying the conduct/context and its role in the article, without reproducing sensitive content. There is no automatic keyword, sentence-count or word-count threshold. A short court brief can qualify when its central subject is a sexual-violence proceeding. Several passing mentions can still be incidental. A single sentence usually does not suffice when it is unrelated background, but can carry the central issue in a genuinely short report.

Policy, advocacy, statistical, survey and opinion pieces qualify when they substantively discuss GBV mechanisms, harms, responses or prevention. A generic equality announcement with no such content is negative. Historical reporting qualifies when GBV remains the main subject; a historical aside does not.

Researcher finalization adopts this centrality-plus-meaningful-content rule, its incidental boundary and genre coverage. If the supplied text is sufficient yet the boundary remains genuinely indeterminate, record semantic `borderline` with a reason. Do not broaden the definition simply to match model output.

## 7. Allegations, truth status and difficult cases

Use neutral reasoning: “the article reports an allegation/proceeding/discussion of …”. Neither conviction nor independent corroboration is required for relevance. Acquittals, withdrawn charges and reports challenging an allegation can still be substantively about sexual or gender-based violence. Do not convert a relevance label into a finding that violence occurred or that a named person committed it. Negation affects what is asserted, but does not automatically remove the topic.

| Case | v1.0 handling |
| --- | --- |
| Allegation, conviction, acquittal or false-allegation discussion | Apply substantiveness to the reported topic; retain the article's uncertainty and procedural status. |
| Court follow-up with no new incident | Positive if the qualifying GBV proceeding remains central and intelligible; no new incident is required. |
| Child sexual violence | Positive when substantive; avoid identifiable child information in reasons or public reporting. |
| Intimate-partner or family dispute | Positive only when abusive conduct is supported; ordinary disagreement is negative, sufficient but ambiguous context is borderline. |
| Unclear perpetrator–victim relationship | Do not infer intimacy or gender motive from sex/kinship; explicit sexual violence can independently qualify. |
| Generic violence against women | Examine mechanism and context; victim gender alone is insufficient. Explicit discussion of gender-directed violence can qualify. |
| Multiple incidents/topics | Judge the whole article using the substantiveness rule; do not create multiple L2 article counts. |
| Historical case | Positive if central; negative if only incidental background in an unrelated story. |
| Policy, advocacy, statistics, survey or opinion | Positive for substantive GBV discussion; negative for generic gender discussion or a passing statistic. |
| Foreign incident in a Kenyan publisher, Kenyan abroad, Kenyan event with foreign context or multi-country story | Geographic eligibility remains an L1/sampling issue. Once eligible, apply the same L2 semantic test; flag doubtful eligibility separately rather than encoding it as `not_gbv`. |
| Sensational headline versus body | Verified body and full context control; do not infer rape, abuse or femicide from a sensational headline. |
| Quotation, denial, negation or metaphor | Determine whether the article substantively discusses qualifying conduct, rather than relying on literal keyword presence. |
| Duplicate or syndicated story | Semantic rule stays the same; sampling and protected-boundary exclusions belong to the protocol. |
| Truncated, corrupt or incomplete extraction | If the missing evidence prevents a semantic decision, use `unable_to_determine`; document the extraction problem separately. |
| Swahili, Sheng, euphemism or code-switching | Use contextual meaning and qualified language competence; do not translate mechanically into a keyword test. |

## 8. Multilingual guidance and evidence priority

Apply one conceptual GBV definition across languages. Review English, Swahili, Sheng and code-switched text in context, including idioms, speaker attribution, negation and euphemism. An unfamiliar expression is not proof of either GBV or non-GBV. Seek a qualified bilingual review through the approved unresolved/adjudication procedure. Do not guess, treat a machine translation as ground truth, or force every mixed article into a single language.

Record language independently from the GBV decision. Describe predominant language, meaningful code-switching and uncertainty under the approved language policy. Swahili reporting from Taifa Leo should strengthen coverage, while Swahili from other publishers and English/mixed text from Taifa Leo remain possible. Sheng is assessed from actual usage, not publisher identity. Its non-standard spelling and overlap with conversational English–Swahili require locally competent interpretation.

A mixed-language headline and body must be interpreted together, preserving each speaker's meaning; the headline's language does not determine the body's language or GBV label. Record meaningful mixtures under the approved conventions rather than treating the headline as the whole article.

Evidence priority is:

1. Full verified body of the **pinned extraction version**, read as a whole.
2. Its headline and internal context, interpreted against the body.
3. Publication and provenance metadata for eligibility/context, not as proof of GBV.

Do not browse external articles, current versions, social media, court files or earlier model/weak answers to fill semantic gaps unless an approved amendment authorizes and records a separate evidence procedure. Do not replace the pinned extraction silently. Human reading is not limited to the model's 512-token maximum; the model's truncated input is a possible error mechanism, not a human evidence limit. Raw language metadata is unvalidated, including known legacy Taifa Leo template-language concerns.

## 9. Human decision procedure

1. Verify the assigned article/version and whether the provided body is sufficiently readable. If crucial evidence is unavailable or language competence is inadequate, choose `unable_to_determine`, leave the label NULL and record the limitation.
2. Identify whether qualifying violence/abuse is substantively reported or discussed under Section 6. If clearly absent, choose `not_gbv`.
3. Check that conduct and GBV context are supported rather than inferred from victim sex, keywords or publisher. If both are supported and substantive, choose `gbv`.
4. If sufficient readable evidence is genuinely ambiguous or conflicting on relevance, choose `borderline` and explain the semantic ambiguity.
5. If the approved review policy requires another qualified decision before acceptance, choose `needs_adjudication`, leave the label NULL and document the question to resolve. Follow the protocol's adjudication limitations; do not invent a second review.
6. Save the independent reason before seeing the model comparison. Preserve the initial decision. Any later permitted revision must remain append-only and have a documented evidence-based reason under the approved acceptance policy.

## 10. Synthetic reviewer examples

Every row below is an invented teaching scenario. It is not an excerpt, paraphrase or inferred label from the private corpus. Short wording is illustrative; the assumed readable context stated in each row matters. Swahili and especially the plausible Sheng/mixed usage need qualified linguistic review before approved reviewer training.

| Example provenance | Invented scenario and assumed article context | v1.0 outcome | Reason |
| --- | --- | --- | --- |
| Synthetic example — not from the collected corpus. | English report centrally describes an allegation that a partner beat and threatened a spouse. | `gbv` | Substantive intimate-partner abuse; allegation status is preserved. |
| Synthetic example — not from the collected corpus. | English report describes a woman losing a handbag to a street thief; no sexual or gendered abuse context is present. | `not_gbv` | Theft and victim sex alone do not establish GBV. |
| Synthetic example — not from the collected corpus. | English homicide report describes conflicting accounts: one alleges partner coercion, another describes an unrelated attack; sufficient readable evidence cannot resolve the article's qualifying context. | `borderline` | Genuine conflicting GBV evidence; victim sex or an absent motive alone would not justify borderline. |
| Synthetic example — not from the collected corpus. | Swahili: “Mume anadaiwa kumpiga mkewe na kumtishia.” The body centrally discusses the alleged abuse and survivor support. | `gbv` | Substantive allegation of partner violence; not a guilt finding. |
| Synthetic example — not from the collected corpus. | Swahili: “Mwanamke aliibiwa simu sokoni.” The readable body describes ordinary theft without qualifying abuse. | `not_gbv` | No supported GBV mechanism. |
| Synthetic example — not from the collected corpus. | English–Swahili: “She says alilazimishwa kufanya ngono.” The body explains alleged sexual coercion and access to support. | `gbv` | Code-switching does not change the sexual-violence definition. |
| Synthetic example — not from the collected corpus. | Plausible Sheng/mixed usage: “Ex wake hum-threaten akimkataa.” The full body explains coercive threats by an ex-partner and their harm. | `gbv` | Meaningful coercive-control context; locally competent interpretation required. |
| Synthetic example — not from the collected corpus. | Mixed-language story repeatedly says “walikosana” but adequate readable context leaves ordinary disagreement and abusive control genuinely indistinguishable. | `borderline` | Semantic uncertainty, rather than keyword-triggered inclusion. |
| Synthetic example — not from the collected corpus. | Sheng expressions are central to a readable report, but the assigned reviewer cannot interpret their contextual meaning. | `unable_to_determine`; NULL label | Reviewer competence limitation, not a semantic negative. |
| Synthetic example — not from the collected corpus. | A policy article explains proposed protection orders, coercive control and survivor access to services. | `gbv` | Substantive discussion can qualify without a new incident. |
| Synthetic example — not from the collected corpus. | A generic announcement of more women in leadership makes a passing mention of violence in a list. | `not_gbv` | GBV is incidental to the article's central purpose. |
| Synthetic example — not from the collected corpus. | An advocacy article explains FGM harms and a campaign's prevention approach. | `gbv` | Substantive prevention/harm discussion. |
| Synthetic example — not from the collected corpus. | A survey article explains reported partner abuse, measurement limitations and help-seeking barriers. | `gbv` | Substantive GBV statistics/discussion; no prevalence validation is implied. |
| Synthetic example — not from the collected corpus. | A short court follow-up centrally reports an acquittal in a sexual-assault proceeding with sufficient context. | `gbv` | Topic relevance remains despite acquittal. |
| Synthetic example — not from the collected corpus. | An anniversary article centrally examines an old GBV prosecution and its implications for survivor protection. | `gbv` | Historical relevance can be substantive. |
| Synthetic example — not from the collected corpus. | A road-opening story briefly mentions an old rape trial unrelated to the infrastructure report. | `not_gbv` | Incidental historical mention fails centrality. |
| Synthetic example — not from the collected corpus. | A sensational headline suggests abuse; the full body clearly describes only an ordinary contract dispute. | `not_gbv` | Body controls; headline implication is unsupported. |
| Synthetic example — not from the collected corpus. | Only a headline survives and the body is corrupt; alleged conduct cannot be assessed. | `unable_to_determine`; NULL label | Insufficient evidence, not semantic borderline. |
| Synthetic example — not from the collected corpus. | A report substantively discusses disputed rape allegations and later withdrawal of charges. | `gbv` | Relevance concerns the reported topic, not factual adjudication. |
| Synthetic example — not from the collected corpus. | A sufficiently readable ambiguous case requires a second qualified ruling under the approved review policy. | `needs_adjudication`; NULL label | Record a referral, not an invented final label. |

## 11. Reviewer conduct and privacy

Reviewers must read the assigned text, use this definition consistently, and record a concise rationale before model feedback. Do not infer labels from source, model confidence, aggregate class counts or past weak decisions. Do not change a label merely to agree with the model. Repeated articles and prior exposure must be declared because interface blinding cannot erase memory.

Reasons should describe conduct/context and relevance without names, identifying victim details or unnecessary quotations. Store decisions, disagreements, article identifiers and any detailed error examples privately in the established protected workflow. Public documentation may contain aggregate methodological evidence and clearly synthetic examples only. Do not invent reviewers, decisions, approvals or translations. Uncertainty is an admissible outcome.

## 12. Versioning and change control

Before an actual batch, archive this finalized document's exact content and checksum, named owner, researcher finalization date, required external approval evidence and guideline identifier in the private research record. Pin the agreed companion protocol and model identity too. The existing app stores a guideline **string**, not the document contents or supervisor signature. Configuring `HUMAN_REVIEW_GUIDELINE_VERSION` to the finalized identifier is a later operational step; this task changes no configuration.

Material changes to semantics, genre coverage or reviewer procedure require a new version and approval. Do not silently relabel a frozen reference set or reuse a version identifier for changed definitions. Record deviations, initial/final review provenance, evidence for revisions and adjudication outcomes privately. Keep the public change log free of article/version/reference identifiers. Formatting-only changes must still be documented and preserve the approved archived copy.

**Implementation gap:** the current workflow does not archive approved codebook content, enforce reviewer linguistic competence, run independent A/B annotation or adjudication, or prevent post-feedback revisions before completion. The [sampling protocol](l2_validation_sampling_protocol_v1.0.md#12-implementation-cross-check-and-gaps) distinguishes enforceable software behavior from proposed research controls. These gaps are not implemented by this documentation task.

## Change Log

| Version | Date | Change | Approval |
| --- | --- | --- | --- |
| 1.0 | 7 October 2026 | Initial draft operational L2 definitions, five-publisher scope, multilingual guidance and synthetic examples; linked to proposed validation protocol. | Pending |
| 1.0 | 7 October 2026 | Researcher confirmed finalization; recorded the existing v1.0 semantic rules as finalized and separated remaining sampling/execution controls. No classifier, labels or runtime configuration changed. | Researcher-confirmed; separate supervisor/ethics approval not asserted |

## Remaining research governance and execution decisions

- **Completed — L2 codebook semantics:** researcher-finalized domains, victim coverage, substantiveness/incidental rule, genre handling and semantic-versus-workflow uncertainty. Any later substantive change requires a new version; finalization does not retroactively relabel the corpus.
- **TODO SUPERVISOR / RESEARCH DECISION — documentary reconciliation:** record required proposal/ethics amendment evidence, Citizen TV/Citizen Digital mapping, named owner, approval and effective date. The researcher's five-publisher instruction is already specified; seven-source engineering inclusion is not formal approval.
- **TODO SUPERVISOR DECISION — language competence:** approve language identification conventions, bilingual/Sheng competence, translation limits and linguistic validation of the synthetic training examples.
- **TODO SUPERVISOR DECISION — review acceptance:** approve second-review coverage, adjudication and initial-versus-post-feedback accepted-reference policy through the companion protocol. Do not represent workflow agreement as independent truth.
