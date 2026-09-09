"""Logging handler that checkpoints a run log to GCS without local persistence."""

from __future__ import annotations

import logging


class GCSRunLogHandler(logging.Handler):
    def __init__(self, storage, object_name: str):
        super().__init__()
        self.storage = storage
        self.object_name = object_name
        existing = storage.read_bytes("runs", object_name)
        self.lines = existing.decode("utf-8").splitlines() if existing else []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.lines.append(self.format(record))
            self.storage.write_bytes(
                "runs",
                self.object_name,
                ("\n".join(self.lines) + "\n").encode(),
                "text/plain; charset=utf-8",
            )
        except Exception:
            self.handleError(record)
