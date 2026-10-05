"""Export private existing binary bootstrap labels; performs no cloud writes."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from annotations.l2_training import build_bootstrap


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    try:
        from database.repositories.annotations import AnnotationRepository
        from database.session import create_session_factory
        from storage import GCSStorage
        manifest = build_bootstrap(AnnotationRepository(create_session_factory()), GCSStorage(), args.output_dir, args.limit)
    except Exception as exc:
        print(f"Bootstrap export stopped ({type(exc).__name__}); check compatible weak labels, storage and a new private output path.", file=sys.stderr)
        return 2
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
