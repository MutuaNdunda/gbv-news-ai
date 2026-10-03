"""Synchronize validated planning CSVs from an anonymous, read-only Google Sheet."""

from __future__ import annotations

import argparse
from contextlib import nullcontext
import csv
from dataclasses import dataclass
import io
import json
import os
from pathlib import Path
import re
import tempfile

import requests


ROOT = Path(__file__).resolve().parents[1]
ROADMAP_DIR = ROOT / "docs/roadmap"
CONFIG_PATH = ROADMAP_DIR / "source.json"
TIMEOUT = (10, 30)
PUBLIC_ACCESS_HELP = (
    "The spreadsheet must allow anonymous read-only access (Anyone with the link: Viewer). "
    "This command does not use Google credentials; choose another authentication "
    "mechanism explicitly if the roadmap cannot be public."
)
TABS = {
    "roadmap": ("Roadmap", "ROADMAP_ROADMAP_GID", (
        "Phase", "Workstream", "Task", "Output / Definition of Done", "Depends On", "Priority", "Status",
    )),
    "current_state": ("Current State", "ROADMAP_CURRENT_STATE_GID", ()),
    "stage_gates": ("Stage Gates", "ROADMAP_STAGE_GATES_GID", (
        "Stage", "Entry Criterion", "Main Work", "Exit Criterion",
    )),
    "annotation_layers": ("Annotation Layers", "ROADMAP_ANNOTATION_LAYERS_GID", (
        "Layer", "Gate / Task", "Primary Question", "Label Structure", "What Must Be Built",
        "Automation / Pre-Annotation", "Human Review", "Entry Criterion", "Exit Criterion",
    )),
}


class RoadmapSyncError(RuntimeError):
    """An actionable source, download, or validation error."""


@dataclass(frozen=True)
class Sheet:
    key: str
    title: str
    spreadsheet_id: str
    gid: str
    headers: tuple[str, ...]

    @property
    def url(self) -> str:
        return (f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}"
                f"/export?format=csv&gid={self.gid}")


def configured_sheets(config_path=CONFIG_PATH, selected=None, environ=None) -> list[Sheet]:
    """Use checked-in public identifiers, with environment overrides and no .env read."""
    environ = os.environ if environ is None else environ
    try:
        config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RoadmapSyncError(f"Cannot read roadmap configuration: {config_path}") from exc
    if not isinstance(config, dict) or not isinstance(config.get("gids"), dict):
        raise RoadmapSyncError("Roadmap source.json must contain spreadsheet_id and gids")
    identifier = environ.get("ROADMAP_SPREADSHEET_ID", config.get("spreadsheet_id", ""))
    if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", identifier):
        raise RoadmapSyncError("Set the public spreadsheet ID in docs/roadmap/source.json or ROADMAP_SPREADSHEET_ID")
    keys = [selected] if selected else list(TABS)
    if any(key not in TABS for key in keys):
        raise RoadmapSyncError("Unknown roadmap worksheet")
    sheets = []
    for key in keys:
        title, variable, headers = TABS[key]
        gid = str(environ.get(variable, config["gids"].get(key, "")))
        if not re.fullmatch(r"\d+", gid):
            raise RoadmapSyncError(f"Set the {title} worksheet GID in source.json or {variable}")
        if key == "current_state":
            configured_headers = config.get("current_state_headers")
            if (not isinstance(configured_headers, list) or not configured_headers
                    or not all(isinstance(value, str) and value.strip() for value in configured_headers)):
                raise RoadmapSyncError("Set current_state_headers in source.json from the actual Current State header row")
            headers = tuple(configured_headers)
        sheets.append(Sheet(key, title, identifier, gid, headers))
    if len({sheet.gid for sheet in sheets}) != len(sheets):
        raise RoadmapSyncError("Each selected worksheet must have a distinct GID")
    return sheets


def validate_csv(payload: bytes, sheet: Sheet, content_type="") -> bytes:
    """Validate CSV shape/headers and return deterministic UTF-8 with LF newlines."""
    if "html" in content_type.lower():
        raise RoadmapSyncError(f"{sheet.title}: received HTML instead of CSV. {PUBLIC_ACCESS_HELP}")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise RoadmapSyncError(f"{sheet.title}: response is not UTF-8 CSV") from exc
    start = text.lstrip().lower()
    if start.startswith(("<!doctype", "<html", "<head", "<body", "<?xml")):
        raise RoadmapSyncError(f"{sheet.title}: received a login/error page instead of CSV. {PUBLIC_ACCESS_HELP}")
    if "\x00" in text:
        raise RoadmapSyncError(f"{sheet.title}: CSV contains NUL characters")
    try:
        rows = list(csv.reader(io.StringIO(text, newline=""), strict=True))
    except csv.Error as exc:
        raise RoadmapSyncError(f"{sheet.title}: malformed CSV") from exc
    while rows and not any(rows[-1]):
        rows.pop()
    if len(rows) < 2:
        raise RoadmapSyncError(f"{sheet.title}: CSV must contain headers and planning rows")
    headers = [value.strip() for value in rows[0]]
    if any(not value for value in headers) or len(set(headers)) != len(headers):
        raise RoadmapSyncError(f"{sheet.title}: empty or duplicate CSV headers")
    missing = [value for value in sheet.headers if value not in headers]
    if missing:
        raise RoadmapSyncError(f"{sheet.title}: missing required columns: {', '.join(missing)}")
    if any(len(row) != len(headers) for row in rows[1:]):
        raise RoadmapSyncError(f"{sheet.title}: inconsistent CSV row width")
    output = io.StringIO(newline="")
    csv.writer(output, lineterminator="\n").writerows(rows)
    return output.getvalue().encode("utf-8")


def download_sheet(session, sheet: Sheet, temporary_path=None) -> bytes:
    try:
        response = session.get(sheet.url, timeout=TIMEOUT)
        response.raise_for_status()
    except requests.HTTPError as exc:
        code = exc.response.status_code if exc.response is not None else "unknown"
        raise RoadmapSyncError(f"{sheet.title}: CSV export returned HTTP {code}. {PUBLIC_ACCESS_HELP}") from exc
    except requests.RequestException as exc:
        raise RoadmapSyncError(f"{sheet.title}: CSV export failed ({type(exc).__name__}); check network access") from exc
    payload = response.content
    if temporary_path is not None:
        temporary_path.write_bytes(payload)
        payload = temporary_path.read_bytes()
    return validate_csv(payload, sheet, response.headers.get("Content-Type", ""))


def replace_snapshots(destination: Path, changes: dict[str, bytes]) -> None:
    """Stage all downloads before per-file atomic replacement, rolling back I/O failures."""
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".roadmap-sync-", dir=destination) as temp:
        staging = Path(temp)
        previous = {}
        for name, payload in changes.items():
            target = destination / name
            previous[name] = target.read_bytes() if target.exists() else None
            (staging / name).write_bytes(payload)
        replaced = []
        try:
            for name in changes:
                (staging / name).replace(destination / name)
                replaced.append(name)
        except OSError:
            for name in reversed(replaced):
                if previous[name] is None:
                    (destination / name).unlink()
                else:
                    backup = staging / name
                    backup.write_bytes(previous[name])
                    backup.replace(destination / name)
            raise


def sync_roadmap(sheets, destination=ROADMAP_DIR, check=False, session=None) -> dict[str, str]:
    """Download/validate the whole selection before any local snapshots are changed."""
    destination = Path(destination)
    if session is None:
        with requests.Session() as anonymous:
            # Prevent implicit ~/.netrc authentication, proxy credentials, or ADC/OAuth.
            anonymous.trust_env = False
            return sync_roadmap(sheets, destination, check, anonymous)
    # Normal sync stages response bytes before validation. Check mode uses memory
    # exclusively so even a missing output directory causes no filesystem writes.
    staging = nullcontext(None) if check else tempfile.TemporaryDirectory(prefix="roadmap-download-")
    with staging as temp:
        downloads = {
            f"{sheet.key}.csv": download_sheet(
                session, sheet, Path(temp) / f"{sheet.key}.csv" if temp else None
            ) for sheet in sheets
        }
    results, changes = {}, {}
    for name, payload in downloads.items():
        target = destination / name
        if target.is_file() and target.read_bytes() == payload:
            results[name] = "current"
        else:
            results[name] = "changed" if target.exists() else "missing"
            changes[name] = payload
    if changes and not check:
        replace_snapshots(destination, changes)
    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Download and compare without filesystem changes")
    parser.add_argument("--sheet", choices=list(TABS), help="Sync or check one worksheet only")
    args = parser.parse_args(argv)
    try:
        results = sync_roadmap(configured_sheets(selected=args.sheet), check=args.check)
    except (RoadmapSyncError, OSError) as exc:
        parser.exit(2, f"Roadmap sync failed: {exc}\n")
    for name, status in results.items():
        display = status if args.check or status == "current" else "updated"
        print(f"{name}: {display}")
    if args.check and any(status != "current" for status in results.values()):
        print("Roadmap snapshots differ; run python3 scripts/sync_roadmap.py")
        return 1
    print("Roadmap is current" if args.check else "Roadmap sync complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
