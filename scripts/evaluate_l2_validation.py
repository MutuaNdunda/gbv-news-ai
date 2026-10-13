"""Export completed pinned L2 reference/prediction pairs privately; no inference or writes to DB."""
import argparse
import json
from pathlib import Path
import sys
from sqlalchemy.exc import SQLAlchemyError

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from annotations.l2_training import private_output
from annotations.validation_batches import evaluate_rows
from annotations.evaluation_reports import persist_report
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
        repo=ValidationBatchRepository(create_session_factory())
        batch,rows=repo.evaluation_rows(args.batch,args.final_experiment)
        report,pairs=evaluate_rows(batch,rows)
        # Exact training exclusion is rechecked for research purposes. Synthetic/legacy
        # callers can still use evaluate_rows; the operator CLI fails closed.
        quality=repo.reference_audit(args.batch,verify_training=True)
        quality.pop('audit_candidates')
        if batch.purpose != 'diagnostic' and (quality['issues'] or not batch.protect_from_training):
            raise ValueError('Reference integrity/training exclusion failed; inspect the private audit.')
        if batch.purpose != 'diagnostic' and not quality['training_exclusion_verified']:
            raise ValueError('Exact training exclusion could not be verified.')
        report['reference_quality']=quality
        if any(r['positive_threshold'] is None or r['negative_threshold'] is None for r in pairs):
            raise ValueError('Missing frozen model thresholds; no report can substitute assumed thresholds.')
        report['final_experiment_released']=bool(args.final_experiment and batch.purpose=='final_test')
        persist_report(output,batch,report,pairs)
    except (ValueError,RuntimeError,LookupError) as exc:
        print(str(exc),file=sys.stderr);return 2
    except SQLAlchemyError:
        print('Validation storage unavailable; verify the target and schema preflight.', file=sys.stderr);return 2
    print(report['warning'])
    print(json.dumps({k:report[k] for k in ('total_members','resolved','binary_evaluable','confusion_matrix','metrics','model_abstention_rate')},sort_keys=True))
    return 0

if __name__=='__main__':raise SystemExit(main())
