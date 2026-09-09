"""Google Cloud Storage adapter using Application Default Credentials."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any

from google.api_core.exceptions import NotFound, PreconditionFailed
from google.cloud import storage

from database.session import load_environment


@dataclass(frozen=True)
class ObjectReference:
    uri: str
    generation: str | None


class GCSStorage:
    def __init__(self, client: storage.Client | None = None):
        load_environment()
        self.client = client or storage.Client(
            project=os.environ.get("GCP_PROJECT_ID") or None
        )
        self.buckets = {
            "raw": self._required("GCS_RAW_BUCKET"),
            "processed": self._required("GCS_PROCESSED_BUCKET"),
            "runs": self._required("GCS_RUNS_BUCKET"),
        }

    @staticmethod
    def _required(name: str) -> str:
        value = os.environ.get(name, "").strip()
        if not value:
            raise RuntimeError(f"Missing storage configuration: {name}")
        return value

    def write_bytes(
        self,
        role: str,
        name: str,
        payload: bytes,
        content_type: str,
        *,
        create_only: bool = False,
    ) -> ObjectReference:
        blob = self.client.bucket(self.buckets[role]).blob(name)
        try:
            blob.upload_from_string(
                payload,
                content_type=content_type,
                if_generation_match=0 if create_only else None,
            )
        except PreconditionFailed:
            existing = blob.download_as_bytes()
            if existing != payload:
                raise RuntimeError(f"Refusing to replace existing gs:// object: {name}")
            blob.reload()
        return ObjectReference(
            uri=f"gs://{self.buckets[role]}/{name}",
            generation=str(blob.generation) if blob.generation is not None else None,
        )

    def write_json(
        self, role: str, name: str, value: Any, *, create_only: bool = False
    ) -> ObjectReference:
        payload = (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()
        return self.write_bytes(
            role, name, payload, "application/json; charset=utf-8", create_only=create_only
        )

    def read_bytes(self, role: str, name: str) -> bytes | None:
        try:
            return self.client.bucket(self.buckets[role]).blob(name).download_as_bytes()
        except NotFound:
            return None

    def read_json(self, role: str, name: str) -> Any | None:
        payload = self.read_bytes(role, name)
        return json.loads(payload) if payload is not None else None

    def bucket_accessible(self, role: str) -> bool:
        """Read bucket metadata only; health checks must not create test objects."""
        self.client.bucket(self.buckets[role]).reload()
        return True
