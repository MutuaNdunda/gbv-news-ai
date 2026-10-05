"""Offline artifact reload and <=20 real in-memory predictions; never writes annotations."""
import argparse
from collections import Counter, defaultdict, deque
import json
import logging
import os
from pathlib import Path
import statistics
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# The Hub is offline for artifact loading; GCS/database read access is separate.
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
from annotations.l2 import TransformerPredictor, sha256_file
from annotations.l2_config import L2Config
from annotations.l2_datasets import reference_membership, resolve_label
from annotations.l2_readiness import l2_schema_readiness
from annotations.l2_training import bootstrap_methods, private_output
from annotations.service import load_verified_article


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-path', required=True)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--limit', type=int, default=20)
    parser.add_argument('--device', choices=('auto', 'cuda', 'mps', 'cpu'), default='auto')
    parser.add_argument('--reference-manifest')
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= 20:
        parser.error('--limit must be between 1 and 20')
    output = private_output(args.output_dir)
    if output.exists():
        parser.error('Use a new private output directory')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    from database.session import create_session_factory
    from database.repositories.annotations import AnnotationRepository
    from database.repositories.human_validations import HumanValidationRepository
    from storage import GCSStorage
    sessions = create_session_factory()
    schema = l2_schema_readiness(sessions)
    config = L2Config(model_path=args.model_path, device=args.device, batch_size=2,
                      positive_threshold=.8, negative_threshold=.2)
    tick = perf_counter()
    predictor = TransformerPredictor(config)
    load_seconds = perf_counter() - tick
    repository, reviews, objects = AnnotationRepository(sessions), HumanValidationRepository(sessions), GCSStorage()
    methods = bootstrap_methods()
    membership, reference_status, reference_hash = reference_membership(args.reference_manifest)
    hashes = membership['content_hashes'] | repository.reference_content_hashes(membership['article_ids'], membership['article_version_ids'])
    candidates = repository.select_candidates(['L2'], methods, only_pending=False, eligible_l2_only=True)
    eligible = [row for row in candidates if str(row['id']) not in membership['article_version_ids']
                and str(row['article_id']) not in membership['article_ids'] and row['content_hash'] not in hashes]
    groups = defaultdict(deque)
    for row in eligible:
        groups[row['metadata']['source']].append(row)
    source_support = {key: len(rows) for key, rows in groups.items()}
    selected = []
    while len(selected) < min(args.limit, len(eligible)):
        for source in sorted(groups):
            if groups[source] and len(selected) < args.limit:
                selected.append(groups[source].popleft())
    current = repository.current_for_candidates([row['id'] for row in selected], methods)
    latest = reviews.latest_for_annotations([row.id for (version, layer), row in current.items() if layer == 'L2'])
    labels, times, priorities, failures = Counter(), [], [], Counter()
    for candidate in selected:
        try:
            l1 = current.get((candidate['id'], 'L1'))
            if l1 is None or l1.label != 'kenya':
                raise ValueError('Current L1 Kenya prerequisite is unavailable')
            article = load_verified_article(candidate, objects)
            tick = perf_counter()
            result = predictor.evaluate(article)
            duration = perf_counter() - tick
            weak = current.get((candidate['id'], 'L2'))
            review = latest.get(weak.id) if weak else None
            label, origin, exclusion = resolve_label(weak, review, 'mixed-effective') if weak else (None, None, 'no_weak_label')
            labels[result.label] += 1
            times.append(duration)
            probability = result.evidence['gbv_probability']
            priorities.append({'article_id': str(candidate['article_id']), 'article_version_id': str(candidate['id']),
                               'p_gbv': probability, 'predicted_label': result.label,
                               'distance_to_decision_threshold': min(abs(probability - .8), abs(probability - .2)),
                               'distance_to_half': abs(probability - .5), 'current_label': label,
                               'current_review_status': review['review_decision'] if review else 'not_reviewed',
                               'label_source': origin or ('human_' + review['review_decision'] if review else 'excluded'),
                               'current_label_exclusion': exclusion, 'disagrees_with_current_label': bool(label and label != result.label),
                               'source': article['source'], 'source_cohort_support': source_support[article['source']],
                               'language': article.get('language')})
        except Exception as exc:
            failures[type(exc).__name__] += 1
    report = {'kind': 'bounded_in_memory_engineering_inference_not_evaluation',
              'model_version': predictor.manifest['model_version'], 'model_method_version': predictor.method_version,
              'model_manifest_sha256': sha256_file(Path(args.model_path) / 'model_manifest.json'),
              'offline_reload': 'passed', 'local_files_only': True, 'trust_remote_code': False,
              'hf_hub_offline': True, 'selection': 'deterministic_round_robin_by_source_not_evaluation_sampling',
              'use_safetensors': True, 'device': predictor.device, 'model_load_seconds': load_seconds,
              'selected': len(selected), 'processed': len(times), 'failed': sum(failures.values()),
              'failure_types': dict(failures), 'labels': {key: labels[key] for key in ('gbv', 'not_gbv', 'borderline')},
              'mean_inference_seconds': statistics.mean(times) if times else None,
              'median_inference_seconds': statistics.median(times) if times else None,
              'schema_readiness': schema, 'database_predictions_written': 0,
              'held_out_reference_status': reference_status, 'reference_manifest_sha256': reference_hash,
              'research_metrics': None, 'positive_threshold': .8, 'negative_threshold': .2,
              'threshold_status': 'UNVALIDATED ENGINEERING THRESHOLDS'}
    output.mkdir(parents=True, exist_ok=False)
    (output / 'inference_report.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    priorities.sort(key=lambda row: (row['distance_to_half'], not row['disagrees_with_current_label'],
                                    row['predicted_label'] != 'gbv', row['source_cohort_support']))
    (output / 'review_priorities.jsonl').write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in priorities))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 2 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
