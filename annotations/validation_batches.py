"""Reproducible sampling and verified training membership, without model inference."""
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import random

from annotations.l2 import model_identity, sha256_file
from annotations.l2_config import L2Config
from annotations.l2_training import ROOT, load_training_data

PURPOSES = ('development_validation', 'final_test', 'diagnostic')
STRATEGIES = ('random', 'stratified', 'enriched')
EMPTY_MEMBERSHIP = {'article_ids': set(), 'article_version_ids': set(), 'content_hashes': set()}


def training_membership(config=None):
    """Fail closed unless the exact model's checksummed training records are available."""
    config = config or L2Config.from_env()
    manifest, method = model_identity(config)
    matches = []
    for path in sorted((ROOT / 'data' / 'l2').rglob('dataset_manifest.json')):
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if data.get('dataset_version') == manifest['training_dataset_version']:
            matches.append(path)
    if not matches:
        raise ValueError('The exact model training dataset manifest is unavailable; independent selection is blocked.')
    path = next((p for p in matches if sha256_file(p) == manifest.get('training_dataset_manifest_sha256')), None)
    if path is None:
        raise ValueError('Training dataset manifest checksum does not match the model artifact.')
    records, dataset = load_training_data(path.parent, manifest['training_dataset_version'])
    if (dataset['records_sha256'] != manifest['training_dataset_sha256']
            or len(records) != manifest.get('training_record_count', len(records))):
        raise ValueError('Training membership does not match the evaluated artifact.')
    membership = {key: {str(r[{'article_ids': 'article_id', 'article_version_ids': 'article_version_id',
                              'content_hashes': 'content_hash'}[key]]) for r in records}
                  for key in EMPTY_MEMBERSHIP}
    return {'membership': membership, 'model_version': manifest['model_version'],
            'method_version': method, 'manifest_sha256': sha256_file(path),
            'model_manifest_sha256': sha256_file(Path(config.model_path) / 'model_manifest.json'),
            'dataset_version': dataset['dataset_version'], 'record_count': len(records)}


def excluded(candidate, membership):
    return (str(candidate['article_id']) in membership['article_ids']
            or str(candidate['id']) in membership['article_version_ids']
            or candidate['content_hash'] in membership['content_hashes'])


def sample(candidates, size, strategy, seed, purpose):
    """Random/round-robin proportional strata never use predicted labels for independence."""
    if purpose not in PURPOSES or strategy not in STRATEGIES or size < 1:
        raise ValueError('Invalid purpose, sampling strategy or sample size.')
    if strategy == 'enriched' and purpose != 'diagnostic':
        raise ValueError('Enriched sampling is allowed only for diagnostic error analysis.')
    if size > len(candidates):
        kind = 'unseen eligible' if purpose != 'diagnostic' else 'eligible diagnostic'
        raise ValueError(f'Only {len(candidates)} {kind} records are available. Collect additional articles before creating this validation batch.')
    rng = random.Random(seed)
    ordered = sorted(candidates, key=lambda r: str(r['annotation_id']))
    if strategy == 'enriched':
        rng.shuffle(ordered)
        ordered.sort(key=lambda r: (r['label'] not in ('gbv', 'borderline'), abs(r['probability'] - .5)))
    elif strategy == 'random':
        rng.shuffle(ordered)
    else:
        # Proportional allocation by source/language metadata, without label enrichment.
        groups = defaultdict(list)
        for row in ordered:
            groups[row['stratum']].append(row)
        allocations = {k: size * len(v) // len(ordered) for k, v in groups.items()}
        remainders = sorted(groups, key=lambda k: (-(size * len(groups[k]) % len(ordered)), k))
        for key in remainders[:size - sum(allocations.values())]:
            allocations[key] += 1
        ordered = []
        for key in sorted(groups):
            rng.shuffle(groups[key])
            ordered.extend(groups[key][:allocations[key]])
        rng.shuffle(ordered)
    return ordered[:size]


def membership_digest(rows):
    payload = [{k: str(r[k]) for k in ('article_id', 'id', 'annotation_id', 'content_hash', 'source', 'language', 'stratum')}
               for r in rows]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def evaluate_rows(batch, rows):
    """Evaluate frozen accepted labels only; exclude human uncertainty and model abstentions."""
    if batch.status != 'completed':
        raise ValueError('Complete the batch to freeze accepted human references before evaluation.')
    if len(rows) != batch.requested_size:
        raise ValueError('Completed membership size mismatch.')
    snapshot = [dict(article_id=m.article_id, id=m.article_version_id, annotation_id=m.automated_annotation_id,
                     content_hash=m.content_hash, source=m.source, language=m.language, stratum=m.sampling_stratum)
                for m, _, _ in rows]
    if membership_digest(snapshot) != batch.configuration['membership_sha256']:
        raise ValueError('Frozen membership digest mismatch.')
    human, model = Counter(gbv=0, not_gbv=0, borderline=0), Counter(gbv=0, not_gbv=0, borderline=0)
    matrix = Counter(TP=0, FP=0, TN=0, FN=0)
    exported = []; unresolved = 0; abstained = 0
    for member, annotation, review in rows:
        if (annotation is None or annotation.id != member.automated_annotation_id or annotation.article_id != member.article_id
                or annotation.article_version_id != member.article_version_id
                or annotation.method_name != batch.model_method_name or annotation.method_version != batch.model_method_version
                or annotation.evidence.get('model_version') != batch.model_version):
            raise ValueError('Pinned model lineage mismatch.')
        if (review is None or not member.initial_human_validation_id or review.id != member.final_human_validation_id
                or review.automated_annotation_id != annotation.id or review.article_id != member.article_id
                or review.article_version_id != member.article_version_id or review.guideline_version != batch.guideline_version):
            raise ValueError('Missing accepted human reference or mismatched review lineage.')
        probability = annotation.evidence.get('gbv_probability')
        if not isinstance(probability, (float, int)) or not math.isfinite(probability) or not 0 <= probability <= 1:
            raise ValueError('Pinned model probability is invalid.')
        h = review.human_label if review.review_decision in ('confirmed', 'corrected') else None
        human[h or review.review_decision] += 1; model[annotation.label] += 1
        unresolved += h is None
        abstained += annotation.label == 'borderline'
        if h in ('gbv', 'not_gbv') and annotation.label in ('gbv', 'not_gbv'):
            matrix['TP' if h == 'gbv' and annotation.label == 'gbv' else
                   'FN' if h == 'gbv' else 'FP' if annotation.label == 'gbv' else 'TN'] += 1
        exported.append({'member_id': str(member.id), 'article_id': str(member.article_id),
                         'article_version_id': str(member.article_version_id), 'annotation_id': str(annotation.id),
                         'initial_human_validation_id': str(member.initial_human_validation_id),
                         'final_human_validation_id': str(review.id), 'human_label': h,
                         'human_decision': review.review_decision, 'model_label': annotation.label,
                         'gbv_probability': annotation.evidence.get('gbv_probability'),
                         'model_version': batch.model_version, 'method_version': batch.model_method_version,
                         'stratum': member.sampling_stratum, 'selection_order': member.selection_order,
                         'adjudication_status': 'pending' if review.review_decision == 'needs_adjudication' else 'not_adjudicated'})
    n = sum(matrix.values());tp,fp,tn,fn = (matrix[x] for x in ('TP','FP','TN','FN'))
    ratio = lambda a,b: a/b if b else None
    diagnostic = batch.purpose == 'diagnostic'
    metrics = None if diagnostic else {'accuracy': ratio(tp+tn,n), 'precision': ratio(tp,tp+fp),
                'recall': ratio(tp,tp+fn), 'f1': ratio(2*tp,2*tp+fp+fn)}
    return {'batch_id': str(batch.id), 'batch_name': batch.name, 'purpose': batch.purpose,
            'model_version': batch.model_version, 'method_version': batch.model_method_version,
            'sampling_strategy': batch.sampling_strategy, 'seed': batch.seed, 'configuration': batch.configuration,
            'total_members': len(rows), 'reviewed': len(rows), 'resolved': len(rows)-unresolved,
            'unresolved': unresolved, 'human_labels': dict(sorted(human.items())), 'model_labels': dict(sorted(model.items())),
            'binary_evaluable': n, 'excluded_from_binary_metrics': len(rows)-n,
            'confusion_matrix': dict(matrix), 'metrics': metrics,
            'model_abstention_rate': ratio(abstained,len(rows)),
            'metric_policy': 'conditional_on_binary_human_labels_and_non_abstaining_model; not whole-corpus accuracy',
            'weighting': 'none; proportional stratification uses largest-remainder allocation, finite-sample rounding remains',
            'warning': 'DIAGNOSTIC / ENRICHED: error analysis only; no representative/population metrics.' if diagnostic else
                       'Metrics describe this unseen reviewed sample; subgroup support and abstentions limit generalization.',
            'roc_auc': None, 'pr_auc': None, 'calibration': None}, exported
