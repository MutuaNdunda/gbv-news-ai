"""Run versioned L0/L1/L2 annotations over persisted trial article versions."""

import argparse
from contextlib import contextmanager
from dataclasses import replace
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from annotations.schemas import DEFAULT_CONFIG
from annotations.l2_config import L2Config
from annotations.service import run_annotation_pipeline


@contextmanager
def prevent_idle_sleep(enabled):
    """Keep a macOS model CLI run awake; never reconnect a lost database lease."""
    if not enabled or sys.platform != "darwin":
        yield
        return
    process = subprocess.Popen(
        ["/usr/bin/caffeinate", "-i", "-w", str(os.getpid())],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        if process.poll() is not None:
            raise RuntimeError("Could not prevent idle sleep for the model run")
        logging.getLogger(__name__).info("annotation_idle_sleep_prevented")
        yield
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def main(argv=None):
    from database.session import load_environment
    load_environment()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layer", required=True, choices=("l0", "l1", "l2", "l0,l1", "l1,l2", "l0,l1,l2"))
    parser.add_argument("--l2-mode", choices=("model", "weak"), default="model",
                        help="Explicit bootstrap mode; never a fallback for a missing model")
    parser.add_argument("--model-path")
    parser.add_argument("--positive-threshold", type=float)
    parser.add_argument("--negative-threshold", type=float)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--force", action="store_true", help="Append new decisions; preserve historical rows")
    parser.add_argument("--collection-run-id", type=UUID)
    parser.add_argument("--article-id", type=UUID, action="append")
    parser.add_argument("--minimum-body-chars", type=int, default=DEFAULT_CONFIG.minimum_body_chars)
    parser.add_argument("--l1-gazetteer", choices=("v1", "v2"), default=DEFAULT_CONFIG.l1_gazetteer)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        config = replace(DEFAULT_CONFIG, minimum_body_chars=args.minimum_body_chars, l1_gazetteer=args.l1_gazetteer)
        l2_config = L2Config.from_env() if "l2" in args.layer else None
        overrides = {key: getattr(args, key) for key in ("model_path", "positive_threshold", "negative_threshold")
                     if getattr(args, key) is not None}
        if l2_config is not None:
            l2_config = replace(l2_config, **overrides)
        with prevent_idle_sleep("l2" in args.layer.split(",") and args.l2_mode == "model"):
            summary = run_annotation_pipeline(args.layer.split(","), args.limit, args.article_id,
                                              args.collection_run_id, not args.force, config=config,
                                              l2_mode=args.l2_mode, l2_config=l2_config)
    except Exception as exc:
        if "l2" in args.layer and isinstance(exc, ValueError):
            print("L2 configuration unavailable: install a trained local artifact and verify thresholds/manifest, "
                  "or explicitly select --l2-mode weak for bootstrap labels.", file=sys.stderr)
        print(f"Annotation run stopped ({type(exc).__name__}); verify configuration and apply the annotation migration.",
              file=sys.stderr)
        return 2
    print(json.dumps(summary, indent=2))
    return 2 if summary["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
