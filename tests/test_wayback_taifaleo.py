"""Bounded local Taifa Leo trials preserve actual captures and reuse snapshots."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from scrapers import wayback

HTML = (Path(__file__).parent / "fixtures/taifaleo_archive_article.html").read_text()
HEADER = ["timestamp", "original", "statuscode", "mimetype"]


class LocalTaifaLeoTests(unittest.TestCase):
    def test_all_date_query_matches_supplied_scope_and_limit(self):
        query = wayback.cdx_params("taifaleo.nation.co.ke", None, None, 500)
        self.assertEqual(query["url"], "taifaleo.nation.co.ke/*")
        self.assertEqual(query["limit"], "500")
        self.assertNotIn("from", query)
        self.assertNotIn("to", query)
        dated = wayback.cdx_params("taifaleo.nation.co.ke", "20260101", "20260131", 500)
        self.assertEqual(dated["to"], "20260131")

    def test_two_attempt_cap_preserves_raw_and_actual_capture(self):
        urls = [f"https://taifaleo.nation.co.ke/shule-ya-majaribio-{i}/" for i in range(3)]
        payload = [HEADER, *[["20221012000000", url, "200", "text/html"] for url in urls]]

        def fetch(url, stage=None):
            if stage == "CDX_INDEX":
                self.assertEqual(parse_qs(urlsplit(url).query)["limit"], ["500"])
                return Mock(status_code=200, json=lambda: payload)
            original = url.split("id_/", 1)[1]
            body = HTML.replace("https://taifaleo.nation.co.ke/shule-yapokea-vifaa-vipya/", original)
            body = body.replace("Shule ya majaribio", "Shule " + original)
            return Mock(status_code=200, url=url.replace("20221012000000", "20221013000000"),
                        content=body.encode(), headers={"Content-Type": "text/html"})

        client = Mock(fetch=Mock(side_effect=fetch))
        with TemporaryDirectory() as temp, patch.object(wayback.time, "sleep"):
            root = Path(temp)
            counts = wayback.process_source(
                source="taifaleo", domain="taifaleo.nation.co.ke", from_date=None, to_date=None,
                raw_root=root / "raw", processed_root=root / "processed",
                cdx_limit=500, max_articles=5, max_fetches=2, session=Mock(), client=client,
            )
            self.assertEqual(counts["fetch_attempts"], 2)
            self.assertEqual(counts["articles_written"], 2)
            self.assertEqual(counts["stop_reason"], "fetch_limit")
            self.assertEqual(len(list((root / "raw/taifaleo").glob("*.html"))), 2)
            records = [json.loads(line) for line in (root / "processed/taifaleo.jsonl").read_text().splitlines()]
            self.assertTrue(all(item["archive_capture_timestamp"] == "20221013000000" for item in records))
            self.assertTrue(all("20221012000000id_/" in item["requested_url"] for item in records))
            self.assertTrue(all(Path(item["raw_snapshot_path"]).exists() for item in records))
            self.assertTrue(all(item["parser_version"] == "taifaleo-archive-1.1" for item in records))

    def test_index_failure_is_not_treated_as_empty_coverage(self):
        client = Mock()
        client.fetch.return_value = None
        with self.assertRaises(RuntimeError):
            wayback.fetch_cdx("taifaleo.nation.co.ke", None, None, 500, Mock(), client)

    def test_cli_failure_replaces_stale_success_manifest(self):
        client = Mock(last_failure={"kind": "ReadTimeout"})
        client.fetch.return_value = None
        with TemporaryDirectory() as temp:
            processed = Path(temp) / "processed"
            processed.mkdir()
            manifest = processed / "taifaleo.manifest.json"
            manifest.write_text(json.dumps({"articles_written": 2}))
            argv = ["wayback.py", "--sources", "taifaleo", "--all-dates", "--limit", "500",
                    "--max-articles", "2", "--max-fetches", "2",
                    "--raw-root", str(Path(temp) / "raw"), "--processed-root", str(processed)]
            with patch.object(wayback.sys, "argv", argv), \
                    patch.object(wayback, "Client", return_value=client), \
                    patch("builtins.print"), self.assertLogs("wayback", level="ERROR"):
                self.assertEqual(wayback.main(), 2)
            result = json.loads(manifest.read_text())
        self.assertEqual(result["status"], "failed")
        self.assertIsNone(result["cdx_rows"])
        self.assertEqual(result["request_failure"]["kind"], "ReadTimeout")

    def test_unchanged_raw_capture_is_reused_without_fetching_again(self):
        original = "https://taifaleo.nation.co.ke/shule-yapokea-vifaa-vipya/"
        # Distinct CDX original and canonical URL force the second invocation to
        # inspect the cached snapshot before canonical/content deduplication.
        alias = "https://taifaleo.nation.co.ke/shule-yapokea-vifaa-majaribio/"
        payload = [HEADER, ["20221012000000", alias, "200", "text/html"]]
        client = Mock()
        client.fetch.side_effect = [Mock(status_code=200, json=lambda: payload),
            Mock(status_code=200, url="https://web.archive.org/web/20221013000000id_/" + original,
                 content=HTML.encode()), Mock(status_code=200, json=lambda: payload)]
        with TemporaryDirectory() as temp, patch.object(wayback.time, "sleep"):
            options = dict(source="taifaleo", domain="taifaleo.nation.co.ke", from_date=None, to_date=None,
                           raw_root=Path(temp) / "raw", processed_root=Path(temp) / "processed",
                           cdx_limit=500, max_articles=2, max_fetches=2, session=Mock(), client=client)
            self.assertEqual(wayback.process_source(**options)["articles_written"], 1)
            counts = wayback.process_source(**options)
        self.assertEqual(counts["snapshots_reused"], 1)
        self.assertEqual(counts["fetch_attempts"], 0)
        self.assertEqual(counts["skipped_duplicate"], 1)
        self.assertEqual(client.fetch.call_count, 3)


if __name__ == "__main__":
    unittest.main()
