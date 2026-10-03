"""Execute current-result window queries against synthetic SQL rows offline."""

from datetime import datetime, timedelta, timezone
import unittest
from uuid import uuid4

from sqlalchemy import Column, JSON, MetaData, Table, create_engine, select, text
from sqlalchemy.dialects.postgresql import JSONB

from database.models import AutomatedAnnotation
from database.repositories.annotations import current_annotations


class CurrentAnnotationQueryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        self.connection = self.engine.connect()
        self.connection.execute(text("ATTACH DATABASE ':memory:' AS public"))
        # SQLite supports the window query. Only replace PostgreSQL JSONB's DDL
        # type for this synthetic table; the production query remains unchanged.
        self.table = Table("automated_annotations", MetaData(), *(
            Column(column.name, JSON() if isinstance(column.type, JSONB) else column.type)
            for column in AutomatedAnnotation.__table__.columns
        ), schema="public")
        self.table.create(self.connection)
        self.version_id = uuid4()
        self.tick = datetime(2026, 10, 3, tzinfo=timezone.utc)

    def tearDown(self):
        self.connection.close()
        self.engine.dispose()

    def add(self, layer, label, method_version=None, prerequisite=None):
        self.tick += timedelta(seconds=1)
        row_id = uuid4()
        self.connection.execute(self.table.insert().values(
            id=row_id, article_id=uuid4(), article_version_id=self.version_id,
            annotation_run_id=uuid4(), prerequisite_annotation_id=prerequisite,
            layer=layer, label=label, method_version=method_version or f"{layer.lower()}-v1.0",
            method_name="synthetic", created_at=self.tick, evidence={}, reason_codes=[],
        ))
        return row_id

    def current_ids(self):
        current = current_annotations({"L0": "l0-v1.0", "L1": "l1-v1.0"})
        return set(self.connection.scalars(select(current.c.id)))

    def test_new_custom_l0_l1_does_not_hide_compatible_default_results(self):
        default_l0 = self.add("L0", "valid")
        default_l1 = self.add("L1", "kenya", prerequisite=default_l0)
        custom_l0 = self.add("L0", "valid", "l0-v1.0-custom")
        self.add("L1", "not_kenya", prerequisite=custom_l0)
        self.assertEqual(self.current_ids(), {default_l0, default_l1})

    def test_latest_l0_gates_l1_and_preserves_all_historical_rows(self):
        old_l0 = self.add("L0", "valid")
        self.add("L1", "kenya", prerequisite=old_l0)
        latest_l0 = self.add("L0", "valid")
        self.assertEqual(self.current_ids(), {latest_l0})
        new_l1 = self.add("L1", "ambiguous", prerequisite=latest_l0)
        self.assertEqual(self.current_ids(), {latest_l0, new_l1})
        invalid_l0 = self.add("L0", "invalid")
        self.assertEqual(self.current_ids(), {invalid_l0})
        self.assertEqual(len(self.connection.execute(select(self.table.c.id)).all()), 5)


if __name__ == "__main__":
    unittest.main()
