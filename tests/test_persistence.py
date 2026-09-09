"""Offline persistence ordering, failure, and idempotency checks."""

import hashlib
import unittest
from uuid import uuid4

from storage.persistence import CollectionPersistence, IndexingError
from tests.storage_fakes import FakeArticles, FakeObjects


def article():
    text = "Synthetic article body"
    return {
        "source": "citizen",
        "canonical_url": "https://citizen.digital/news/example-n1",
        "title": "Example",
        "author": "",
        "published_at": "2026-08-10T10:00:00+03:00",
        "scraped_at": "2026-09-09T10:00:00+00:00",
        "article_text": text,
        "content_hash": hashlib.sha256(text.encode()).hexdigest(),
        "parser_version": "citizen-archive-test",
        "publication_month": "2026-08",
    }


class PersistenceTests(unittest.TestCase):
    def test_raw_precedes_processed_and_database_and_retry_is_idempotent(self):
        objects, articles = FakeObjects(), FakeArticles()
        service = CollectionPersistence(objects, articles)
        item = article()
        raw = service.store_raw("citizen", item["canonical_url"], b"<html/>", "2026-08")
        self.assertEqual(objects.writes[0][0], "raw")
        self.assertTrue(service.persist_article(item, raw, uuid4()))
        self.assertEqual(objects.writes[1][0], "processed")
        self.assertFalse(service.persist_article(item, raw, uuid4()))
        self.assertEqual(len(articles.versions), 1)

    def test_raw_failure_prevents_downstream_writes(self):
        class FailingObjects(FakeObjects):
            def write_bytes(self, *args, **kwargs):
                raise RuntimeError("GCS unavailable")

        articles = FakeArticles()
        with self.assertRaises(RuntimeError):
            CollectionPersistence(FailingObjects(), articles).store_raw(
                "citizen", article()["canonical_url"], b"raw", "2026-08"
            )
        self.assertFalse(articles.items)

    def test_database_failure_keeps_both_gcs_artifacts_for_retry(self):
        objects, articles = FakeObjects(), FakeArticles()
        service = CollectionPersistence(objects, articles)
        item = article()
        raw = service.store_raw("citizen", item["canonical_url"], b"raw", "2026-08")
        articles.fail_persist = True
        with self.assertRaises(IndexingError) as raised:
            service.persist_article(item, raw, uuid4())
        self.assertEqual([role for role, _ in objects.writes], ["raw", "processed"])
        articles.fail_persist = False
        writes_before_retry = len(objects.writes)
        self.assertTrue(service.retry_index(raised.exception.pending, uuid4()))
        self.assertEqual(len(objects.writes), writes_before_retry)


if __name__ == "__main__":
    unittest.main()
