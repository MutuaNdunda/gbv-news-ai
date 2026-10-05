"""Prediction-write readiness and the real inference bound require no cloud access."""
import unittest
from unittest.mock import Mock, patch

from annotations.l2_readiness import l2_schema_readiness


class L2ReadinessTests(unittest.TestCase):
    def check(self, checks=None, indexes=None, triggers=None):
        inspector = Mock()
        inspector.get_check_constraints.return_value = checks or []
        inspector.get_indexes.return_value = indexes or []
        session = Mock()
        session.execute.return_value.mappings.return_value.all.return_value = triggers or []
        sessions = Mock(kw={'bind': Mock()})
        sessions.return_value.__enter__ = Mock(return_value=session)
        sessions.return_value.__exit__ = Mock(return_value=False)
        with patch('annotations.l2_readiness.inspect', return_value=inspector):
            return l2_schema_readiness(sessions)

    def test_existing_weak_rows_or_partial_schema_do_not_establish_readiness(self):
        state = self.check()
        self.assertFalse(state['ready_for_prediction_writes'])
        self.assertEqual(len(state['missing']), 4)
        self.assertFalse(state['migration_installed_by_check'])

    def test_expected_constraints_index_and_enabled_trigger_required(self):
        checks = [dict(name='automated_annotations_l2_label_check', sqltext="L2 gbv not_gbv borderline"),
                  dict(name='automated_annotations_l2_prerequisite_check', sqltext="L2 prerequisite_annotation_id IS NOT NULL")]
        indexes = [dict(name='idx_auto_annotations_l2_identity', column_names=[
            'article_version_id', 'method_name', 'method_version', 'prerequisite_annotation_id', 'created_at'],
            dialect_options={'postgresql_where': "layer = 'L2'"})]
        trigger = dict(tgname='automated_annotations_l2_prerequisite', tgenabled='O',
                       trigger_definition='BEFORE INSERT OR UPDATE', function_definition=' '.join([
                           'L1', 'kenya', 'p.article_id = NEW.article_id',
                           'p.article_version_id = NEW.article_version_id', 'p.id = NEW.prerequisite_annotation_id']))
        self.assertTrue(self.check(checks, indexes, [trigger])['ready_for_prediction_writes'])
        self.assertFalse(self.check(checks, indexes, [{**trigger, 'tgenabled': 'D'}])['ready_for_prediction_writes'])

    def test_inference_limit_enforced_before_cloud_access(self):
        from scripts.check_l2_model import main
        for limit in ('0', '21'):
            with patch('sys.stderr'), self.assertRaises(SystemExit) as exc:
                main(['--model-path', 'unused', '--output-dir', 'unused', '--limit', limit])
            self.assertEqual(exc.exception.code, 2)
