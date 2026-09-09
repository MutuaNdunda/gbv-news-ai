"""Safely validate Supabase PostgreSQL and Google Cloud Storage access."""

from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Callable
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_TABLES = (
    "public.collection_runs",
    "public.articles",
    "public.article_versions",
    "public.collection_run_scans",
)
BUCKETS = (
    ("raw bucket", "GCS_RAW_BUCKET"),
    ("processed bucket", "GCS_PROCESSED_BUCKET"),
    ("runs bucket", "GCS_RUNS_BUCKET"),
)
TEST_PAYLOAD = b"gbv-news-ai infrastructure connection test\n"
NETWORK_TIMEOUT_SECONDS = 10


def required_environment(name: str) -> str:
    """Return a required setting without ever displaying its value."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"missing environment variable {name}")
    return value


def test_supabase() -> tuple[bool, bool]:
    """Run read-only connection and schema checks against Supabase PostgreSQL."""
    from sqlalchemy import URL, create_engine, text

    try:
        port = int(required_environment("DB_PORT"))
        if not 1 <= port <= 65535:
            raise ValueError("DB_PORT must be between 1 and 65535")
        url = URL.create(
            drivername="postgresql+psycopg",
            username=required_environment("DB_USER"),
            password=required_environment("DB_PASSWORD"),
            host=required_environment("DB_HOST"),
            port=port,
            database=required_environment("DB_NAME"),
            query={"sslmode": "require"},
        )
    except (TypeError, ValueError):
        return False, False

    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": NETWORK_TIMEOUT_SECONDS},
    )
    try:
        with engine.connect() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            database_name, database_user = connection.execute(
                text("SELECT current_database(), current_user")
            ).one()
            connection_ok = bool(database_name and database_user)
            found = {
                table_name
                for table_name, exists in connection.execute(
                    text(
                        "SELECT required.name, to_regclass(required.name) IS NOT NULL "
                        "FROM unnest(CAST(:tables AS text[])) AS required(name)"
                    ),
                    {"tables": list(REQUIRED_TABLES)},
                )
                if exists
            }
            tables_ok = found == set(REQUIRED_TABLES)
            connection.rollback()
            return connection_ok, tables_ok
    except Exception:  # The result stays secret-safe; exception text is not printed.
        return False, False
    finally:
        engine.dispose()


def test_gcs() -> tuple[dict[str, bool], bool]:
    """Check bucket access and temporary-object create/read/delete permissions."""
    from google.cloud import storage

    results = {label: False for label, _ in BUCKETS}
    permissions_ok = True
    try:
        configured = [
            (label, required_environment(variable))
            for label, variable in BUCKETS
        ]
        project = os.environ.get("GCP_PROJECT_ID", "").strip() or None
        client = storage.Client(project=project)
    except Exception:
        return results, False

    for label, bucket_name in configured:
        bucket = client.bucket(bucket_name)
        try:
            bucket.reload(timeout=NETWORK_TIMEOUT_SECONDS, retry=None)
            results[label] = True
        except Exception:
            permissions_ok = False
            continue

        blob = bucket.blob(f"_connection_test/{uuid4()}.txt")
        uploaded = False
        try:
            blob.upload_from_string(
                TEST_PAYLOAD,
                content_type="text/plain; charset=utf-8",
                if_generation_match=0,
                timeout=NETWORK_TIMEOUT_SECONDS,
                retry=None,
            )
            uploaded = True
            if blob.download_as_bytes(
                timeout=NETWORK_TIMEOUT_SECONDS,
                retry=None,
            ) != TEST_PAYLOAD:
                permissions_ok = False
        except Exception:
            permissions_ok = False
        finally:
            if uploaded:
                try:
                    blob.delete(
                        if_generation_match=blob.generation,
                        timeout=NETWORK_TIMEOUT_SECONDS,
                        retry=None,
                    )
                except Exception:
                    permissions_ok = False

    return results, permissions_ok and all(results.values())


def run_check(name: str, check: Callable[[], bool]) -> bool:
    """Print one concise, consistently formatted result."""
    try:
        passed = bool(check())
    except Exception:
        passed = False
    print(f"{'PASS' if passed else 'FAIL'} {name}")
    return passed


def main() -> int:
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except Exception:
        # Report every required check even when configuration support is unavailable.
        pass

    try:
        database_ok, tables_ok = test_supabase()
    except Exception:
        database_ok, tables_ok = False, False

    try:
        bucket_results, object_permissions_ok = test_gcs()
    except Exception:
        bucket_results = {label: False for label, _ in BUCKETS}
        object_permissions_ok = False

    results = [
        run_check("Supabase connection", lambda: database_ok),
        run_check("required Supabase tables", lambda: tables_ok),
    ]
    results.extend(
        run_check(f"GCS {label}", lambda value=value: value)
        for label, value in bucket_results.items()
    )
    results.append(
        run_check(
            "GCS write/read/delete permissions",
            lambda: object_permissions_ok,
        )
    )
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
