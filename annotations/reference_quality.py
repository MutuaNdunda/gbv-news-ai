"""Metadata-only reference audit. Never use model disagreement for quality sampling."""
from collections import Counter, defaultdict
import math
import random

from annotations.validation_batches import membership_digest, excluded


def evidence_basis(review):
    notes = (getattr(review, 'notes', None) or '').lower()
    if 'title-only decision; verified body not opened' in notes:
        return 'title_only'
    if 'verified body opened' in notes:
        return 'verified_body_access'
    return 'other_unknown'


def reference_label(review):
    return review.human_label if review and review.review_decision in ('confirmed', 'corrected') else None


def assess_references(batch, rows, training=None, articles=None, initials=None, versions=None):
    """Audit pinned pointers, not the latest global review. No scientific acceptance inferred."""
    articles, initials, versions = articles or {}, initials or {}, versions or {}
    counts = Counter(); labels = Counter(); evidence = Counter(); reviewers = set()
    issues = []; candidates = []; snapshot = []; hashes = Counter()
    for member, annotation, review in rows:
        snapshot.append(dict(article_id=member.article_id, id=member.article_version_id,
            annotation_id=member.automated_annotation_id, content_hash=member.content_hash,
            source=member.source, language=member.language, stratum=member.sampling_stratum))
        hashes[member.content_hash] += 1
        counts['initial_pointers'] += bool(member.initial_human_validation_id)
        counts['final_pointers'] += bool(member.final_human_validation_id)
        valid_model = bool(annotation and annotation.id == member.automated_annotation_id
            and annotation.article_id == member.article_id and annotation.article_version_id == member.article_version_id
            and annotation.layer == 'L2' and annotation.method_name == batch.model_method_name
            and annotation.method_version == batch.model_method_version
            and annotation.evidence.get('model_version') == batch.model_version)
        valid_review = bool(review and review.id == member.final_human_validation_id
            and review.automated_annotation_id == member.automated_annotation_id
            and review.article_id == member.article_id and review.article_version_id == member.article_version_id
            and review.layer == 'L2' and review.guideline_version == batch.guideline_version)
        if not valid_model: counts['model_lineage_issues'] += 1
        if valid_model:
            p=annotation.evidence.get('gbv_probability')
            pos=annotation.evidence.get('positive_threshold'); neg=annotation.evidence.get('negative_threshold')
            numeric=lambda v: not isinstance(v,bool) and isinstance(v,(int,float)) and math.isfinite(v)
            if not numeric(p) or not 0 <= p <= 1:
                counts['model_probability_issues'] += 1
            elif not numeric(pos) or not numeric(neg) or not 0 <= neg < pos <= 1:
                counts['model_threshold_issues'] += 1
            elif annotation.label != ('gbv' if p >= pos else 'not_gbv' if p <= neg else 'borderline'):
                counts['model_threshold_issues'] += 1
        if not valid_review: counts['reference_lineage_issues'] += 1
        if initials:
            initial = initials.get(member.initial_human_validation_id)
            if not initial or (initial.automated_annotation_id, initial.article_id, initial.article_version_id,
                               initial.guideline_version, initial.layer) != (member.automated_annotation_id,
                               member.article_id, member.article_version_id, batch.guideline_version, 'L2'):
                counts['initial_lineage_issues'] += 1
            pointer = review.id if review else None; visited = set()
            while pointer and pointer != member.initial_human_validation_id and pointer not in visited:
                visited.add(pointer)
                ancestor = initials.get(pointer)
                if not ancestor or (ancestor.automated_annotation_id, ancestor.article_id, ancestor.article_version_id) != (
                        member.automated_annotation_id, member.article_id, member.article_version_id):
                    pointer = None; break
                pointer = ancestor.supersedes_validation_id
            if pointer != member.initial_human_validation_id:
                counts['reference_chain_issues'] += 1
        if versions:
            version = versions.get(member.article_version_id)
            if not version or version.article_id != member.article_id or version.content_hash != member.content_hash:
                counts['extraction_lineage_issues'] += 1
        label = reference_label(review) if valid_review else None
        expected_status = ('resolved' if label in ('gbv','not_gbv','borderline') else
                           review.review_decision if valid_review else 'pending')
        if member.status != expected_status:
            counts['member_status_issues'] += 1
        labels[label or (review.review_decision if valid_review else 'missing_invalid')] += 1
        counts['resolved_binary'] += label in ('gbv', 'not_gbv')
        counts['resolved_semantic'] += label in ('gbv', 'not_gbv', 'borderline')
        basis = evidence_basis(review) if valid_review else 'other_unknown'
        evidence[basis] += 1
        if valid_review:
            reviewers.add(review.reviewer_identity)
        if training and excluded(snapshot[-1], training['membership']): counts['training_overlap'] += 1
        article = articles.get(member.article_id)
        counts['missing_publication_metadata'] += not article or not article.published_at
        counts['unknown_language_metadata'] += not member.language
        candidates.append(dict(member_id=str(member.id), article_id=str(member.article_id),
            annotation_id=str(member.automated_annotation_id), source=member.source,
            language=member.language or 'unknown', human_label=label, evidence_basis=basis,
            title=article.title if article else None))
    digest = membership_digest(snapshot)
    integrity = len(rows) == batch.requested_size and digest == batch.configuration.get('membership_sha256')
    if not integrity: issues.append('Frozen membership count or digest mismatch.')
    issue_keys = ('model_lineage_issues', 'reference_lineage_issues', 'initial_lineage_issues',
                  'extraction_lineage_issues', 'reference_chain_issues', 'member_status_issues',
                  'model_probability_issues', 'model_threshold_issues')
    for key in issue_keys:
        if counts[key]: issues.append(f'{key}: {counts[key]}')
    duplicate_count = sum(n - 1 for n in hashes.values())
    if duplicate_count: issues.append('Exact duplicate bodies in batch.')
    training_verified = bool(training and training['model_version'] == batch.model_version
        and training['method_version'] == batch.model_method_version
        and training['manifest_sha256'] == batch.configuration.get('training_manifest_sha256')
        and training['model_manifest_sha256'] == batch.configuration.get('model_manifest_sha256'))
    if training and (not training_verified or counts['training_overlap']):
        issues.append('Training provenance mismatch or training overlap.')
    warnings = [
        'Near-duplicate, incident and syndicated-story independence is not established; no cluster-aware intervals.',
        'Language metadata is unverified. Publisher identity does not establish language.',
        'Archive sampling and source exclusions limit representativeness; no fairness-disparity claim.',
        'No independent A/B decisions or adjudication instrument; inter-annotator agreement is unavailable.',
        'Configured reviewer identities are not independently authenticated people.',
        'Reference acceptance and codebook/protocol reconciliation require researcher approval.']
    if evidence['title_only']:
        warnings.insert(0, 'Title-only reference labels: review-evidence limitation. Full-context codebook verification remains needed.')
    if evidence['verified_body_access']:
        warnings.append('Verified body access records opening, not correct reading or labeling.')
    if batch.guideline_version != 'l2-gbv-relevance-codebook-v1.0':
        warnings.append('Frozen guideline identifier differs from the named finalized codebook; do not silently replace it.')
    return dict(batch_id=str(batch.id), batch_name=batch.name, purpose=batch.purpose, status=batch.status,
        model_version=batch.model_version, method_version=batch.model_method_version,
        guideline_version=batch.guideline_version, configuration=batch.configuration,
        sampling_strategy=batch.sampling_strategy, seed=batch.seed, protected=batch.protect_from_training,
        requested=batch.requested_size, total_members=len(rows), membership_sha256=digest,
        membership_integrity=integrity, counts={k:counts[k] for k in sorted(set(counts)|set(issue_keys)|{'training_overlap'})},
        member_status_counts={k:sum(m.status==k for m,_,_ in rows) for k in ('pending','resolved','unable_to_determine','needs_adjudication')},
        human_labels=dict(labels),
        evidence_basis=dict(evidence), title_only_fraction=evidence['title_only']/len(rows) if rows else None,
        recorded_reviewer_identity_count=len(reviewers),
        source_counts=dict(Counter(m.source for m, _, _ in rows)),
        language_counts=dict(Counter(m.language or 'unknown' for m, _, _ in rows)),
        exact_duplicate_count=duplicate_count, training_exclusion_verified=training_verified,
        technical_integrity_ready=bool(not issues and training_verified and batch.protect_from_training),
        technical_ready=bool(batch.status == 'completed' and not issues and training_verified
                             and batch.protect_from_training),
        reference_quality_ready='requires_researcher_acceptance', issues=issues, warnings=warnings,
        audit_candidates=candidates)


def blinded_audit_sample(candidates, per_stratum=2, seed=20261013):
    """Proposed sample, never an assignment: human label × source × evidence basis."""
    if not 1 <= per_stratum <= 20:
        raise ValueError('Audit sample requires 1–20 records per stratum.')
    groups = defaultdict(list)
    for row in sorted(candidates, key=lambda r: r['member_id']):
        if row['human_label'] in ('gbv', 'not_gbv'):
            groups[(row['human_label'], row['source'], row['evidence_basis'])].append(row)
    rng = random.Random(seed); result = []
    for key in sorted(groups):
        result.extend(rng.sample(groups[key], min(per_stratum, len(groups[key]))))
    rng.shuffle(result)
    return result
