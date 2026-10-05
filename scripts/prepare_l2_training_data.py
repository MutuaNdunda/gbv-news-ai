"""Export private binary weak/reviewed/mixed development labels; no cloud writes."""
import argparse
import json
import logging
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from annotations.l2_training import build_bootstrap
from annotations.l2_datasets import build_development


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--label-policy", choices=("weak-only", "reviewed-only", "mixed-effective"), default="weak-only")
    parser.add_argument("--reference-manifest", help="Private frozen human_reference_test membership manifest")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    try:
        from database.repositories.annotations import AnnotationRepository
        from database.session import create_session_factory
        from storage import GCSStorage
        sessions = create_session_factory()
        repository, objects = AnnotationRepository(sessions), GCSStorage()
        if args.label_policy == "weak-only":
            if args.reference_manifest:
                parser.error("Reference exclusions require an explicit reviewed/mixed policy")
            manifest = build_bootstrap(repository, objects, args.output_dir, args.limit)
        else:
            from database.repositories.human_validations import HumanValidationRepository
            manifest = build_development(repository, HumanValidationRepository(sessions), objects, args.output_dir,
                                         args.label_policy, args.limit, reference_manifest=args.reference_manifest)
    except Exception as exc:
        print(f"L2 development export stopped ({type(exc).__name__}); check compatible labels/reviews, storage and a new private output path.", file=sys.stderr)
        return 2
    print(json.dumps({key: value for key, value in manifest.items() if key != "exclusions"}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
