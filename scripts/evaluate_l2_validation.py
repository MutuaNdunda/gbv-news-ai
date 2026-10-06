"""Export completed pinned L2 reference/prediction pairs privately; no inference or writes to DB."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from sqlalchemy.exc import SQLAlchemyError

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from annotations.l2_training import private_output
from annotations.validation_batches import evaluate_rows
from database.repositories.validation_batches import ValidationBatchRepository
from database.session import create_session_factory


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch',required=True,help='Batch UUID or exact versioned name')
    parser.add_argument('--output-dir',required=True)
    parser.add_argument('--final-experiment',action='store_true',help='Explicit approved final experiment; release sealed final-test results')
    args=parser.parse_args(argv)
    try:
        output=private_output(args.output_dir)
        if not output.is_relative_to(ROOT / 'data'):
            raise ValueError('Evaluation output must be under ignored data/.')
        if output.exists():raise ValueError('Use a new private output directory.')
        batch,rows=ValidationBatchRepository(create_session_factory()).evaluation_rows(args.batch,args.final_experiment)
        report,pairs=evaluate_rows(batch,rows)
        payload=''.join(json.dumps(r,sort_keys=True,ensure_ascii=False)+'\n' for r in pairs)
        report['records_sha256']=hashlib.sha256(payload.encode()).hexdigest()
        serialized=json.dumps(report,sort_keys=True,indent=2,ensure_ascii=False)+'\n'
        output.mkdir(parents=True,exist_ok=False)
        (output/'evaluation_pairs.jsonl').write_text(payload)
        (output/'evaluation_report.json').write_text(serialized)
        (output/'manifest.json').write_text(json.dumps({'batch_id':str(batch.id),'batch_name':batch.name,
            'evaluation_pairs_sha256':report['records_sha256'],'evaluation_report_sha256':hashlib.sha256(serialized.encode()).hexdigest()},sort_keys=True,indent=2)+'\n')
    except (ValueError,RuntimeError,LookupError) as exc:
        print(str(exc),file=sys.stderr);return 2
    except SQLAlchemyError:
        print('Validation storage unavailable; verify the target and schema preflight.', file=sys.stderr);return 2
    print(report['warning'])
    print(json.dumps({k:report[k] for k in ('total_members','resolved','binary_evaluable','confusion_matrix','metrics','model_abstention_rate')},sort_keys=True))
    return 0

if __name__=='__main__':raise SystemExit(main())
