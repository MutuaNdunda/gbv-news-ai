"""Run versioned L0/L1 annotations over persisted trial article versions."""

import argparse
from dataclasses import replace
import json
import logging
from pathlib import Path
import sys
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from annotations.schemas import DEFAULT_CONFIG
from annotations.service import run_annotation_pipeline


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layer", required=True, choices=("l0", "l1", "l0,l1"))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--force", action="store_true", help="Append new decisions; preserve historical rows")
    parser.add_argument("--collection-run-id", type=UUID)
    parser.add_argument("--article-id", type=UUID, action="append")
    parser.add_argument("--minimum-body-chars", type=int, default=DEFAULT_CONFIG.minimum_body_chars)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        config = replace(DEFAULT_CONFIG, minimum_body_chars=args.minimum_body_chars)
        summary = run_annotation_pipeline(args.layer.split(","), args.limit, args.article_id,
                                          args.collection_run_id, not args.force, config=config)
    except Exception as exc:
        print(f"Annotation run stopped ({type(exc).__name__}); verify configuration and apply the annotation migration.",
              file=sys.stderr)
        return 2
    print(json.dumps(summary, indent=2))
    return 2 if summary["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
