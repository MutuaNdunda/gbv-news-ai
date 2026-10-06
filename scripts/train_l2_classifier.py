"""Explicit AfroXLMR binary development training; no reference evaluation."""
import argparse
import json
import os
import logging
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from annotations.l2_config import BASE_MODEL, L2Config
from annotations.l2_training import train_classifier


def main(argv=None):
    from database.session import load_environment
    load_environment()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", required=True)
    parser.add_argument("--dataset-version")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--model-version", required=True)
    parser.add_argument("--base-model", default=os.getenv("L2_BASE_MODEL", BASE_MODEL))
    parser.add_argument("--revision", help="Pin the reviewed Hugging Face commit or use a local base artifact")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--class-weighting", choices=("balanced", "none"), default="balanced")
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-steps", type=int, help="Bound a smoke/development training run")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda", "mps"), default="auto")
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--cache-dir", help="Local Hugging Face cache for a pinned base revision")
    args = vars(parser.parse_args(argv))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        # Recheck protection even for an export created before a batch was frozen.
        from annotations.l2_training import load_training_data
        from annotations.validation_batches import excluded
        from database.repositories.annotations import AnnotationRepository
        from database.session import create_session_factory
        rows, _ = load_training_data(args["dataset_dir"], args["dataset_version"])
        protected = AnnotationRepository(create_session_factory()).protected_membership()
        if any(excluded({"article_id": row["article_id"], "id": row["article_version_id"],
                         "content_hash": row["content_hash"]}, protected) for row in rows):
            raise ValueError("Dataset contains protected reference members; regenerate the development export.")
        result = train_classifier(**args, l2_config=L2Config.from_env())
    except Exception as exc:
        print(f"L2 training stopped ({type(exc).__name__}); verify development manifest, optional dependencies and parameters.", file=sys.stderr)
        return 2
    print(json.dumps({key: result[key] for key in ("model_version", "training_dataset_version", "development_diagnostics")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
