"""Execute L2 dependency/identity resolution against synthetic SQLite rows."""
from sqlalchemy import select, update
import unittest

from annotations.l2_config import MODEL_METHOD, WEAK_METHOD
from database.repositories.annotations import current_annotations
from tests import test_annotation_queries as fixtures


class L2QueryTests(unittest.TestCase):
    setUp = fixtures.CurrentAnnotationQueryTests.setUp
    tearDown = fixtures.CurrentAnnotationQueryTests.tearDown

    def add(self, layer, label, method_version=None, prerequisite=None, method_name=None):
        row_id = fixtures.CurrentAnnotationQueryTests.add(self, layer, label, method_version, prerequisite)
        if layer == "L1":
            self.connection.execute(update(self.table).where(self.table.c.id == row_id).values(
                method_name=method_name or "kenya_relevance_hybrid"))
        return row_id
    def add_l2(self, prerequisite, name=MODEL_METHOD, version="l2-model-test"):
        row_id = self.add("L2", "gbv", version, prerequisite)
        self.connection.execute(update(self.table).where(self.table.c.id == row_id).values(method_name=name))
        return row_id

    def ids(self, model="l2-model-test", name=MODEL_METHOD):
        current = current_annotations({"L0": "l0-v1.0", "L1": "l1-v1.0", "L2": model,
                                       "L2_method_name": name, "L1_method_name": "kenya_relevance_hybrid"})
        return set(self.connection.scalars(select(current.c.id)))

    def test_weak_and_new_incompatible_rows_do_not_hide_model(self):
        l0 = self.add("L0", "valid")
        l1 = self.add("L1", "kenya", prerequisite=l0)
        model = self.add_l2(l1)
        weak = self.add_l2(l1, WEAK_METHOD)
        custom_l1 = self.add("L1", "kenya", "l1-custom", l0)
        self.add_l2(custom_l1)
        self.assertEqual(self.ids(), {l0, l1, model})
        self.assertEqual(self.ids(name=WEAK_METHOD), {l0, l1, weak})

    def test_force_latest_and_l1_replacement_make_l2_historical(self):
        l0 = self.add("L0", "valid")
        old_l1 = self.add("L1", "kenya", prerequisite=l0)
        self.add_l2(old_l1)
        newest = self.add_l2(old_l1)
        self.assertEqual(self.ids(), {l0, old_l1, newest})
        new_l1 = self.add("L1", "kenya", prerequisite=l0)
        self.assertEqual(self.ids(), {l0, new_l1})
        new_l2 = self.add_l2(new_l1)
        self.assertEqual(self.ids(), {l0, new_l1, new_l2})
        self.assertEqual(len(self.connection.execute(select(self.table.c.id)).all()), 6)

    def test_missing_not_kenya_ambiguous_or_invalid_l0_gate(self):
        l0 = self.add("L0", "valid")
        for label in ("not_kenya", "ambiguous", "kenya"):
            l1 = self.add("L1", label, prerequisite=l0)
            l2 = self.add_l2(l1)
            self.assertEqual(l2 in self.ids(), label == "kenya")
        invalid_l0 = self.add("L0", "invalid")
        self.assertEqual(self.ids(), {invalid_l0})

    def test_changed_l2_identity_does_not_reuse_previous_predictions(self):
        l0 = self.add("L0", "valid")
        l1 = self.add("L1", "kenya", prerequisite=l0)
        self.add_l2(l1)
        self.assertEqual(self.ids(model="l2-new-thresholds"), {l0, l1})

    def test_wrong_l1_method_name_does_not_hide_compatible_l1_or_supply_gate(self):
        l0 = self.add("L0", "valid")
        compatible_l1 = self.add("L1", "kenya", prerequisite=l0)
        compatible_l2 = self.add_l2(compatible_l1)
        wrong = self.add("L1", "kenya", prerequisite=l0, method_name="wrong_family")
        self.add_l2(wrong)
        self.assertEqual(self.ids(), {l0, compatible_l1, compatible_l2})
