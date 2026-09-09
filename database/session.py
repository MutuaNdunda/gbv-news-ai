"""Create SQLAlchemy sessions from the project's Supabase settings."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker


ROOT = Path(__file__).resolve().parents[1]


def load_environment() -> None:
    load_dotenv(ROOT / ".env")


def database_url() -> str | URL:
    load_environment()
    if value := os.environ.get("DATABASE_URL", "").strip():
        url = make_url(value)
        if url.drivername in {"postgres", "postgresql"}:
            url = url.set(drivername="postgresql+psycopg")
        return url
    required = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD")
    missing = [name for name in required if not os.environ.get(name, "").strip()]
    if missing:
        raise RuntimeError("Missing database configuration: " + ", ".join(missing))
    return URL.create(
        "postgresql+psycopg",
        username=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=os.environ["DB_HOST"],
        port=int(os.environ["DB_PORT"]),
        database=os.environ["DB_NAME"],
        query={"sslmode": "require"},
    )


def create_database_engine() -> Engine:
    return create_engine(database_url(), pool_pre_ping=True)


def create_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=engine or create_database_engine(), expire_on_commit=False)
