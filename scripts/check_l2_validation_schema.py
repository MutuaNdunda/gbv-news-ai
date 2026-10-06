"""Read-only validation schema preflight; never applies migrations or prints credentials."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from database.repositories.validation_batches import schema_readiness
from database.session import create_session_factory


def main():
    try:
        result = schema_readiness(create_session_factory())
    except Exception as exc:
        print(f'Validation schema preflight failed ({type(exc).__name__}); verify the intended database configuration.',
              file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result['ready'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
