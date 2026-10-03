"""Public roadmap synchronization is testable without Google or network access."""

import csv
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

import requests

from scripts.sync_roadmap import (
    RoadmapSyncError, Sheet, TABS, TIMEOUT, configured_sheets, download_sheet,
    main, replace_snapshots, sync_roadmap, validate_csv,
)


def payload(sheet, value="Planning row"):
    out = io.StringIO(newline="")
    csv.writer(out).writerows([sheet.headers, [value] * len(sheet.headers)])
    return out.getvalue().encode("utf-8")


def response(body, content_type="text/csv"):
    return Mock(content=body, headers={"Content-Type": content_type}, status_code=200)


class RoadmapSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sheets = [Sheet(key, title, "public-test-id", str(index), headers or ("Area", "Current State"))
                       for index, (key, (title, _, headers)) in enumerate(TABS.items())]
        self.session = Mock()
        self.session.get.side_effect = [response(payload(sheet)) for sheet in self.sheets]

    def test_successful_download_validates_all_tabs_and_preserves_unicode(self):
        self.session.get.side_effect = [response(payload(sheet, 'L0 — valid, "review"\nprovenance'))
                                        for sheet in self.sheets]
        result = sync_roadmap(self.sheets, self.root / "roadmap", session=self.session)
        self.assertEqual(set(result.values()), {"missing"})
        self.assertEqual(self.session.get.call_count, 4)
        for sheet in self.sheets:
            path = self.root / "roadmap" / f"{sheet.key}.csv"
            rows = list(csv.reader(io.StringIO(path.read_text(encoding="utf-8"))))
            self.assertEqual(rows[0], list(sheet.headers))
            self.assertEqual(rows[1][0], 'L0 — valid, "review"\nprovenance')
        self.session.get.assert_any_call(self.sheets[0].url, timeout=TIMEOUT)

    def test_missing_headers_are_rejected_for_each_tab(self):
        for sheet in self.sheets:
            with self.subTest(sheet=sheet.key), self.assertRaisesRegex(RoadmapSyncError, "missing required columns"):
                validate_csv(b"Wrong header\nSome content\n", sheet)

    def test_html_error_response_is_rejected_even_with_csv_content_type(self):
        for body, content_type in [(b"<!DOCTYPE html><html>Sign in</html>", "text/csv"),
                                   (b"Login", "text/html")]:
            with self.subTest(content_type=content_type), self.assertRaisesRegex(RoadmapSyncError, "anonymous"):
                download_sheet(Mock(get=Mock(return_value=response(body, content_type))), self.sheets[0])

    def test_failed_final_download_preserves_every_existing_snapshot(self):
        for sheet in self.sheets:
            (self.root / f"{sheet.key}.csv").write_bytes(b"good local snapshot")
        self.session.get.side_effect = [response(payload(sheet)) for sheet in self.sheets[:-1]] + [requests.Timeout()]
        with self.assertRaisesRegex(RoadmapSyncError, "Timeout"):
            sync_roadmap(self.sheets, self.root, session=self.session)
        self.assertEqual({path.read_bytes() for path in self.root.glob("*.csv")}, {b"good local snapshot"})
        self.assertEqual(len(list(self.root.iterdir())), 4)

    def test_validation_failure_preserves_local_files_and_creates_no_directory(self):
        self.session.get.side_effect = [response(payload(self.sheets[0])), response(b"<html>error</html>")]
        target = self.root / "does-not-exist"
        with self.assertRaises(RoadmapSyncError):
            sync_roadmap(self.sheets, target, session=self.session)
        self.assertFalse(target.exists())

    def test_check_reports_difference_without_writing(self):
        target = self.root / "roadmap.csv"
        target.write_bytes(b"original")
        before = target.stat().st_mtime_ns
        result = sync_roadmap(self.sheets[:1], self.root, check=True, session=self.session)
        self.assertEqual(result, {"roadmap.csv": "changed"})
        self.assertEqual(target.read_bytes(), b"original")
        self.assertEqual(target.stat().st_mtime_ns, before)
        self.assertEqual(list(self.root.iterdir()), [target])

    def test_check_missing_directory_does_not_create_it(self):
        target = self.root / "missing"
        result = sync_roadmap(self.sheets[:1], target, check=True, session=self.session)
        self.assertEqual(result, {"roadmap.csv": "missing"})
        self.assertFalse(target.exists())

    def test_repeat_sync_is_idempotent_and_leaves_mtime_unchanged(self):
        sync_roadmap(self.sheets, self.root, session=self.session)
        before = {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in self.root.iterdir()}
        self.session.get.side_effect = [response(payload(sheet)) for sheet in self.sheets]
        self.assertEqual(set(sync_roadmap(self.sheets, self.root, session=self.session).values()), {"current"})
        self.assertEqual(before, {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in self.root.iterdir()})

    def test_bom_crlf_and_csv_quoted_fields_are_normalized_safely(self):
        sheet = self.sheets[0]
        value = "Kenya — evidence, with commas"
        expected = payload(sheet, value).decode().replace("\r\n", "\n").encode()
        self.assertEqual(validate_csv(b"\xef\xbb\xbf" + payload(sheet, value), sheet), expected)

    def test_malformed_utf8_row_width_and_headers_are_rejected(self):
        for body in [b"\xff", b"A,A\n1,2\n", b"A,\n1,2\n", b'"unterminated', b"A\n1,2\n"]:
            with self.subTest(body=body), self.assertRaises(RoadmapSyncError):
                validate_csv(body, Sheet("x", "Example", "id", "0", ("A",)))

    def test_http_failure_has_public_access_instruction(self):
        failed = requests.Response()
        failed.status_code = 403
        self.session.get.side_effect = requests.HTTPError(response=failed)
        with self.assertRaisesRegex(RoadmapSyncError, "HTTP 403.*anonymous"):
            download_sheet(self.session, self.sheets[0])

    def test_config_environment_overrides_and_single_sheet_selection(self):
        config = self.root / "source.json"
        config.write_text(json.dumps({"spreadsheet_id": "default-id", "gids": {"roadmap": "0"}}))
        sheets = configured_sheets(config, "roadmap", {"ROADMAP_SPREADSHEET_ID": "override-id",
                                                        "ROADMAP_ROADMAP_GID": "100"})
        self.assertEqual((sheets[0].spreadsheet_id, sheets[0].gid), ("override-id", "100"))
        with self.assertRaises(RoadmapSyncError):
            configured_sheets(config, "roadmap", {"ROADMAP_SPREADSHEET_ID": "../unsafe"})

    def test_current_state_schema_and_gids_are_required(self):
        config = self.root / "source.json"
        config.write_text(json.dumps({"spreadsheet_id": "id", "gids": {"current_state": "0"}}))
        with self.assertRaisesRegex(RoadmapSyncError, "current_state_headers"):
            configured_sheets(config, "current_state", {})

    def test_production_http_session_disables_implicit_credentials(self):
        with patch("scripts.sync_roadmap.requests.Session") as factory:
            session = factory.return_value.__enter__.return_value
            session.get.return_value = response(payload(self.sheets[0]))
            sync_roadmap(self.sheets[:1], self.root)
            self.assertFalse(session.trust_env)

    def test_atomic_replacement_failure_rolls_back_prior_replacements(self):
        for name in ("roadmap.csv", "current_state.csv"):
            (self.root / name).write_bytes(b"old")
        original = Path.replace

        def replace(path, target):
            if path.name == "current_state.csv":
                raise OSError("synthetic replacement failure")
            return original(path, target)

        with patch.object(Path, "replace", replace), self.assertRaises(OSError):
            replace_snapshots(self.root, {"roadmap.csv": b"new", "current_state.csv": b"new"})
        self.assertEqual((self.root / "roadmap.csv").read_bytes(), b"old")
        self.assertEqual((self.root / "current_state.csv").read_bytes(), b"old")

    def test_check_cli_exit_codes(self):
        with patch("scripts.sync_roadmap.configured_sheets", return_value=self.sheets), \
                patch("scripts.sync_roadmap.sync_roadmap", return_value={"roadmap.csv": "changed"}) as sync, \
                patch("builtins.print"):
            self.assertEqual(main(["--check", "--sheet", "roadmap"]), 1)
            sync.assert_called_once_with(self.sheets, check=True)
        with patch("scripts.sync_roadmap.configured_sheets", return_value=self.sheets), \
                patch("scripts.sync_roadmap.sync_roadmap", return_value={"roadmap.csv": "current"}), \
                patch("builtins.print"):
            self.assertEqual(main(["--check"]), 0)


if __name__ == "__main__":
    unittest.main()
