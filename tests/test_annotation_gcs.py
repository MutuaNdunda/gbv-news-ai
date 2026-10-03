"""Stored-generation reads preserve immutable annotation input lineage."""

import unittest
from unittest.mock import Mock

from google.cloud.exceptions import NotFound

from storage.gcs import GCSStorage


class AnnotationGCSReadTests(unittest.TestCase):
    def setUp(self):
        self.store = object.__new__(GCSStorage)
        self.store.buckets = {"processed": "processed"}
        self.store.client = Mock()
        self.bucket = self.store.client.bucket.return_value
        self.blob = self.bucket.blob.return_value

    def test_pins_recorded_generation_and_decodes_json(self):
        self.blob.download_as_bytes.return_value = b'{"source": "synthetic"}'
        self.assertEqual(self.store.read_json("processed", "article.json", "123"), {"source": "synthetic"})
        self.bucket.blob.assert_called_once_with("article.json", generation=123)
        self.blob.download_as_bytes.assert_called_once_with(timeout=30)

    def test_legacy_read_does_not_invent_a_generation(self):
        self.blob.download_as_bytes.return_value = b"{}"
        self.assertEqual(self.store.read_json("processed", "article.json"), {})
        self.bucket.blob.assert_called_once_with("article.json")

    def test_missing_object_returns_none_but_transient_failures_are_not_hidden(self):
        self.blob.download_as_bytes.side_effect = NotFound("synthetic")
        self.assertIsNone(self.store.read_json("processed", "article.json", "123"))
        self.blob.download_as_bytes.side_effect = RuntimeError("synthetic unavailable")
        with self.assertRaises(RuntimeError):
            self.store.read_json("processed", "article.json", "123")


if __name__ == "__main__":
    unittest.main()
