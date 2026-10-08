"""Diagnose collection ownership read-only; opt in to proven-orphan repair."""
from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import inspect, text
from database.session import create_session_factory
from database.repositories.collection_runs import CollectionRunRepository

CONTROL_COLUMNS = {'last_heartbeat_at', 'stop_requested_at', 'stop_requested_reason',
                   'finalization_reason', 'worker_token'}


def diagnose_legacy(sessions):
    """No SELECT of absent mapped columns, writes or unverifiable orphan claims."""
    with sessions() as session:
        rows = session.execute(text('''
            SELECT r.id, r.run_name, r.started_at,
              (SELECT count(*) FROM public.article_versions v WHERE v.collection_run_id = r.id) AS articles,
              (SELECT count(*) FROM public.collection_run_scans s WHERE s.collection_run_id = r.id) AS scans,
              (SELECT max(updated_at) FROM public.collection_run_scans s WHERE s.collection_run_id = r.id) AS scan_activity
            FROM public.collection_runs r WHERE r.status = 'running' ORDER BY r.started_at DESC
        ''')).mappings().all()
    repository = CollectionRunRepository(sessions)
    from database.repositories.collection_runs import CollectionLockBusy
    from sqlalchemy.exc import DBAPIError
    from database.repositories.collection_runs import CollectionLockLost
    result = []
    for row in rows:
        item = dict(row)
        item.update(last_heartbeat_at=None, action='unchanged_missing_heartbeat', ownership='unknown')
        try:
            with repository.lock(row['run_name']) as lease:
                lease.check()
                item['ownership'] = 'no_owner_at_probe'
        except CollectionLockBusy:
            item['ownership'] = 'active_lock'
        except (DBAPIError, CollectionLockLost):
            item['ownership'] = 'unavailable'
        result.append(item)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--dry-run', action='store_true', help='Default: never change rows')
    group.add_argument('--apply', action='store_true', help='Interrupt only stale managed runs with no lock owner')
    parser.add_argument('--stale-seconds', type=int, default=1800)
    args = parser.parse_args(argv)
    if args.stale_seconds < 60:
        parser.error('stale-seconds must be at least 60')
    sessions = create_session_factory()
    columns = {c['name'] for c in inspect(sessions.kw['bind']).get_columns('collection_runs', schema='public')}
    missing = CONTROL_COLUMNS - columns
    if missing:
        if args.apply:
            parser.error('Apply the collection-control migration first; legacy rows cannot be repaired from age alone')
        rows = diagnose_legacy(sessions)
    else:
        rows = CollectionRunRepository(sessions).reconcile_stale_runs(
            apply=args.apply, stale_seconds=args.stale_seconds)
    print(json.dumps(dict(dry_run=not args.apply, running_count=len(rows),
                          missing_columns=sorted(missing), runs=rows), default=str, indent=2))
    return 0


if __name__ == '__main__':
    from sqlalchemy.exc import SQLAlchemyError
    try:
        raise SystemExit(main())
    except SQLAlchemyError as exc:
        print('Collection diagnostic unavailable: ' + type(exc).__name__, file=sys.stderr)
        raise SystemExit(2)
