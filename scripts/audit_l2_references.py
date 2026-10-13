"""Read-only L2 reference-quality preflight; no scores, body reads or database writes."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from sqlalchemy.exc import SQLAlchemyError

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from annotations.evaluation_reports import serialize, checksum
from annotations.l2_training import private_output
from database.repositories.validation_batches import ValidationBatchRepository
from database.session import create_session_factory


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch',required=True)
    parser.add_argument('--output-dir',required=True, help='New ignored private directory under data/.')
    args=parser.parse_args(argv)
    try:
        output=private_output(args.output_dir)
        if not output.is_relative_to(ROOT/'data') or output.exists():
            raise ValueError('Use a new private directory under data/.')
        audit=ValidationBatchRepository(create_session_factory()).reference_audit(args.batch,verify_training=True)
        audit['observed_at']=datetime.now(timezone.utc).isoformat()
        # Detailed identities/headlines stay in private audit.json; stdout is aggregate only.
        payload=serialize(audit)
        output.mkdir(parents=True,exist_ok=False,mode=0o700)
        (output/'audit.json').write_text(payload); (output/'audit.json').chmod(0o600)
        (output/'manifest.json').write_text(serialize({'audit_sha256':checksum(payload.encode())}))
        (output/'manifest.json').chmod(0o600)
        public=dict(audit);public.pop('audit_candidates')
        print(json.dumps(public,sort_keys=True))
        return 0
    except (ValueError, RuntimeError, LookupError) as exc:
        print(str(exc),file=sys.stderr);return 2
    except SQLAlchemyError:
        print('Private validation storage unavailable; verify the intended database and schema.',file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
