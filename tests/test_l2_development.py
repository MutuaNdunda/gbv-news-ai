"""Reviewed/mixed export uses synthetic articles only; ordinary tests download nothing."""
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import unittest
from unittest.mock import Mock

from annotations.l2_datasets import build_development, load_development, resolve_label
from annotations.l2_training import class_weights, load_training_data, training_provenance
from tests import test_l2_training as training_fixture
from tests.test_l2_ui import L2ReviewFixture


class DevelopmentExportTests(unittest.TestCase):
    setUp = training_fixture.TrainingDataTests.setUp
    add = training_fixture.TrainingDataTests.add
    output = training_fixture.TrainingDataTests.output

    def review(self, item, decision='corrected', label='gbv'):
        weak = self.repository.current_for_candidates([item['id']], __import__('annotations.l2_training', fromlist=['bootstrap_methods']).bootstrap_methods())[(item['id'], 'L2')]
        return weak, dict(id=uuid4(), automated_annotation_id=weak.id, article_id=weak.article_id,
            article_version_id=weak.article_version_id, layer='L2', machine_label=weak.label,
            review_decision=decision, human_label=label, guideline_version='synthetic-v1')

    def export(self, name, policy='mixed-effective', reviews=None, **kwargs):
        repository = Mock()
        repository.latest_for_annotations.return_value = reviews or {}
        return build_development(self.repository, repository, self.objects, self.output(name), policy, **kwargs)

    def test_both_policies_provenance_deterministic_and_loader(self):
        positive, _ = self.add('borderline')
        negative, _ = self.add('borderline')
        confirmed, _ = self.add('not_gbv')
        unreviewed, _ = self.add('gbv')
        borderline, _ = self.add('borderline')
        reviews = {}
        for item, decision, label in [(positive, 'corrected', 'gbv'), (negative, 'corrected', 'not_gbv'),
                                      (confirmed, 'confirmed', 'not_gbv'), (borderline, 'confirmed', 'borderline')]:
            weak, review = self.review(item, decision, label)
            reviews[weak.id] = review
        first = self.export('mixed', reviews=reviews)
        second = self.export('repeat', reviews=reviews)
        self.assertEqual(first, second)
        self.assertEqual(first['label_counts'], {'gbv': 2, 'not_gbv': 2})
        self.assertEqual(first['label_source_counts'], {'human_confirmed': 1, 'human_corrected': 2, 'weak_unreviewed': 1})
        self.assertEqual(first['skipped'], {'borderline': 1})
        rows, loaded = load_training_data(self.output('mixed'))
        self.assertEqual(loaded, first)
        row = next(row for row in rows if row['article_version_id'] == str(positive['id']))
        self.assertEqual(row['machine_label'], 'borderline')
        self.assertEqual(row['label'], 'gbv')
        self.assertEqual(row['human_guideline_version'], 'synthetic-v1')
        self.assertEqual(row['human_validation_id'], str(next(r['id'] for r in reviews.values() if r['article_version_id'] == positive['id'])))
        reviewed = self.export('reviewed', 'reviewed-only', reviews)
        self.assertEqual(reviewed['label_counts'], {'gbv': 1, 'not_gbv': 2})
        self.assertEqual(reviewed['skipped'], {'borderline': 1, 'unreviewed': 1})
        load_training_data(self.output('reviewed'))
        provenance = training_provenance(first, rows)
        self.assertEqual((provenance['gbv_count'], provenance['human_corrected_count'], provenance['weak_unreviewed_count']), (2, 2, 1))
        self.assertEqual(provenance['excluded_borderline_count'], 1)

    def test_resolution_blocks_unresolved_and_borderline_fallback(self):
        item, _ = self.add('gbv')
        weak, review = self.review(item, 'confirmed', 'not_gbv')
        # Confirmation's development target is the machine label.
        self.assertEqual(resolve_label(weak, review, 'mixed-effective')[:2], ('gbv', 'human_confirmed'))
        for decision in ('unable_to_determine', 'needs_adjudication'):
            review.update(review_decision=decision, human_label=None)
            self.assertEqual(resolve_label(weak, review, 'mixed-effective'), (None, None, 'unresolved'))
        review.update(review_decision='corrected', human_label='borderline')
        self.assertEqual(resolve_label(weak, review, 'mixed-effective'), (None, None, 'borderline'))
        self.assertEqual(resolve_label(weak, None, 'reviewed-only'), (None, None, 'unreviewed'))
        self.assertEqual(resolve_label(weak, None, 'mixed-effective')[:2], ('gbv', 'weak_unreviewed'))
        review['article_version_id'] = uuid4()
        with self.assertRaisesRegex(ValueError, 'lineage'):
            resolve_label(weak, review, 'mixed-effective')

    def test_exact_duplicates_and_reference_exclusion_before_storage(self):
        first, _ = self.add('gbv', same_hash=True)
        self.add('gbv', same_hash=True)
        self.add('not_gbv')
        self.repository.candidates.append(first)
        manifest = self.export('dedup')
        self.assertEqual(manifest['record_count'], 2)
        self.assertEqual(manifest['pre_dedup_record_count'], 3)
        self.assertEqual(manifest['skipped'], {'duplicate_article_version': 1, 'duplicate_body_hash': 1})
        self.assertEqual(len(manifest['exclusions']), 2)
        load_development(self.output('dedup'))
        reference = self.output('reference.json')
        reference.write_text(json.dumps({'kind': 'human_reference_test', 'frozen': True,
                                        'article_version_ids': [str(first['id'])]}))
        self.objects.read_json.reset_mock()
        heldout = self.export('excluded', reference_manifest=reference)
        self.assertEqual(heldout['skipped']['held_out_reference'], 2)
        self.assertEqual(heldout['record_count'], 1)
        self.assertEqual(self.objects.read_json.call_count, 1)

    def test_historical_reference_body_is_excluded_by_repository_hash_lookup(self):
        item, _ = self.add('gbv', same_hash=True)
        self.add('not_gbv')
        self.repository.reference_content_hashes = Mock(return_value={item['content_hash']})
        reference = self.output('historical-reference.json')
        reference.write_text(json.dumps({'kind': 'human_reference_test', 'frozen': True,
                                        'article_version_ids': [str(uuid4())]}))
        manifest = self.export('historical-protected', reference_manifest=reference)
        self.assertEqual(manifest['skipped']['held_out_reference'], 1)
        self.assertEqual(manifest['label_counts'], {'not_gbv': 1})
        self.repository.reference_content_hashes.assert_called_once()

    def test_conflicting_duplicate_labels_are_excluded(self):
        self.add('gbv', same_hash=True)
        self.add('not_gbv', same_hash=True)
        manifest = self.export('conflict')
        self.assertEqual(manifest['record_count'], 0)
        self.assertEqual(manifest['skipped']['duplicate_conflicting_labels'], 2)

    def test_incompatible_gate_and_prerequisite_do_not_export(self):
        self.add('gbv', prerequisite=uuid4())
        self.add('not_gbv', l1_label='ambiguous')
        manifest = self.export('gated')
        self.assertEqual(manifest['record_count'], 0)
        self.assertEqual(manifest['skipped']['missing_compatible_weak_label'], 1)
        self.objects.read_json.assert_not_called()

    def test_reference_test_manifests_corruption_and_count_tampering_rejected(self):
        self.add('gbv'); self.add('not_gbv')
        self.export('valid')
        path = self.output('valid') / 'dataset_manifest.json'
        original = json.loads(path.read_text())
        for change in ({'kind': 'human_reference_test'}, {'kind': 'final_test'}, {'split_status': 'test'},
                       {'label_counts': {'gbv': 999}}, {'label_policy': 'reviewed-only'}):
            path.write_text(json.dumps({**original, **change}))
            with self.assertRaises(ValueError):
                load_training_data(self.output('valid'))
        path.write_text(json.dumps(original))
        with self.assertRaisesRegex(ValueError, 'version mismatch'):
            load_training_data(self.output('valid'), 'other')
        records = self.output('valid') / 'development.jsonl'
        records.write_text(records.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            load_training_data(self.output('valid'))

    def test_class_weights_formula_and_configuration(self):
        records = [{'label': 'not_gbv'}] * 8 + [{'label': 'gbv'}] * 2
        self.assertEqual(class_weights(records, 'balanced'), {'not_gbv': .625, 'gbv': 2.5})
        self.assertEqual(class_weights(records, 'none'), {'not_gbv': 1., 'gbv': 1.})
        with self.assertRaises(ValueError):
            class_weights(records, 'unknown')


class LatestReviewExportTests(L2ReviewFixture):
    def test_latest_sql_revision_wins_for_exact_annotation(self):
        values = dict(decision='corrected', human_label='gbv', error_category='other', reason='Synthetic', notes='')
        first = self.service.save_review(self.weak.id, values, 'synthetic', 'synthetic-v1', None)
        latest = self.service.save_review(self.weak.id, {**values, 'human_label': 'not_gbv'}, 'synthetic', 'synthetic-v2', first.id)
        reviews = self.service.reviews.latest_for_annotations([self.weak.id, self.l2[0].id])
        self.assertEqual(set(reviews), {self.weak.id})
        self.assertEqual(reviews[self.weak.id]['id'], latest.id)
        self.assertEqual(resolve_label(self.weak, reviews[self.weak.id], 'mixed-effective')[:2], ('not_gbv', 'human_corrected'))
        self.assertNotIn('notes', reviews[self.weak.id])


class WeightedTrainerTests(unittest.TestCase):
    """Tiny local tensor integration when optional ML dependencies are installed."""
    setUp = DevelopmentExportTests.setUp
    add = DevelopmentExportTests.add
    output = DevelopmentExportTests.output
    review = DevelopmentExportTests.review
    export = DevelopmentExportTests.export
    def test_weighted_trainer_artifact_metadata_and_offline_reload(self):
        from importlib.util import find_spec
        if not all(find_spec(name) for name in ('torch', 'transformers', 'safetensors')):
            self.skipTest('Optional ML runtime is not installed')
        import torch
        from safetensors.torch import save_file, load_file
        from unittest.mock import patch
        from annotations.l2 import TransformerPredictor, read_manifest
        from annotations.l2_config import L2Config
        from annotations.l2_training import train_classifier
        positive, _ = self.add('borderline')
        self.add('not_gbv'); self.add('not_gbv')
        weak, review = self.review(positive)
        self.export('train-data', reviews={weak.id: review})

        class Tokenizer:
            model_max_length = 32
            init_kwargs = {'_commit_hash': 'synthetic-pinned-revision'}
            def __call__(self, texts, **kwargs):
                return {'input_ids': torch.tensor([[len(text) % 7, 1.] for text in texts], dtype=torch.float32)}
            def save_pretrained(self, path):
                (Path(path) / 'tokenizer_config.json').write_text('{}')

        class TinyClassifier(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.head = torch.nn.Linear(2, 2)
                self.config = SimpleNamespace(_commit_hash='synthetic-pinned-revision', num_labels=2,
                    id2label={0: 'not_gbv', 1: 'gbv'}, max_position_embeddings=34, pad_token_id=1)
            def forward(self, input_ids):
                return SimpleNamespace(logits=self.head(input_ids))
            def save_pretrained(self, path, **kwargs):
                save_file(self.state_dict(), str(Path(path) / 'model.safetensors'))
                (Path(path) / 'config.json').write_text('{}')

        tokenizer = Tokenizer()
        model = TinyClassifier()
        with patch('transformers.AutoTokenizer.from_pretrained', return_value=tokenizer) as token_load, \
             patch('transformers.AutoModelForSequenceClassification.from_pretrained', return_value=model) as model_load:
            manifest = train_classifier(self.output('train-data'), self.output('trained'), 'synthetic-dev',
                base_model='synthetic-local', revision='synthetic-pinned-revision', epochs=2, batch_size=2,
                device='cpu', local_files_only=True, class_weighting='balanced')
        self.assertEqual(manifest['training_parameters']['class_weights'], {'not_gbv': .75, 'gbv': 1.5})
        self.assertEqual(manifest['training_parameters']['completed_steps'], 4)
        self.assertEqual(manifest['human_corrected_count'], 1)
        self.assertEqual(manifest['weak_unreviewed_count'], 2)
        self.assertEqual(manifest['training_record_count'], 3)
        self.assertIsNone(manifest['development_diagnostics']['independent_validation_metrics'])
        self.assertGreater(manifest['training_duration_seconds'], 0)
        self.assertTrue(model_load.call_args.kwargs['use_safetensors'])
        self.assertFalse(token_load.call_args.kwargs['trust_remote_code'])
        read_manifest.cache_clear()
        self.assertEqual(read_manifest(str(self.output('trained')))['files_sha256'], manifest['files_sha256'])
        reloaded = TinyClassifier()
        reloaded.load_state_dict(load_file(str(self.output('trained') / 'model.safetensors')))
        token_factory, model_factory = Mock(), Mock()
        token_factory.from_pretrained.return_value = Tokenizer()
        model_factory.from_pretrained.return_value = reloaded
        predictor = TransformerPredictor(L2Config(model_path=str(self.output('trained')), device='cpu'),
                                         runtime=(torch, token_factory, model_factory))
        result = predictor.evaluate({'title': 'Synthetic', 'article_text': 'Synthetic article.'})
        self.assertIn(result.label, ('gbv', 'not_gbv', 'borderline'))
        self.assertFalse(reloaded.training)
        self.assertTrue(model_factory.from_pretrained.call_args.kwargs['local_files_only'])
