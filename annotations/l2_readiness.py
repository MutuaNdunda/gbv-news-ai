"""Read-only installed L2 schema checks; migration files are not installation evidence."""
from sqlalchemy import inspect, text


def l2_schema_readiness(sessions):
    engine = sessions.kw['bind']
    inspector = inspect(engine)
    checks = {row['name']: row['sqltext'] for row in inspector.get_check_constraints('automated_annotations', schema='public')}
    indexes = {row['name']: row for row in inspector.get_indexes('automated_annotations', schema='public')}
    label_sql = checks.get('automated_annotations_l2_label_check', '')
    prerequisite_sql = checks.get('automated_annotations_l2_prerequisite_check', '')
    index = indexes.get('idx_auto_annotations_l2_identity', {})
    with sessions() as session:
        triggers = session.execute(text("""
            SELECT t.tgname, t.tgenabled, pg_get_triggerdef(t.oid) AS trigger_definition,
                   pg_get_functiondef(t.tgfoid) AS function_definition
            FROM pg_trigger t
            WHERE t.tgrelid = 'public.automated_annotations'::regclass AND NOT t.tgisinternal
        """)).mappings().all()
    trigger = next((row for row in triggers if row['tgname'] == 'automated_annotations_l2_prerequisite'), None)
    expected_columns = ['article_version_id', 'method_name', 'method_version', 'prerequisite_annotation_id', 'created_at']
    index_predicate = str(index.get('dialect_options', {}).get('postgresql_where', ''))
    state = {
        'l2_label_constraint': all(term in label_sql for term in ('L2', 'gbv', 'not_gbv', 'borderline')),
        'l2_prerequisite_constraint': 'L2' in prerequisite_sql and 'prerequisite_annotation_id IS NOT NULL' in prerequisite_sql,
        'method_dependency_index': index.get('column_names') == expected_columns and 'L2' in index_predicate,
        'l1_kenya_prerequisite_trigger': bool(trigger and trigger['tgenabled'] in ('O', 'A')
            and 'BEFORE INSERT OR UPDATE' in trigger['trigger_definition']
            and all(term in trigger['function_definition'] for term in (
                'L1', 'kenya', 'p.article_id = NEW.article_id', 'p.article_version_id = NEW.article_version_id',
                'p.id = NEW.prerequisite_annotation_id'))),
    }
    return {'ready_for_prediction_writes': all(state.values()), 'checks': state,
            'missing': [key for key, value in state.items() if not value],
            'migration': '20261005_add_l2_annotations.sql', 'migration_installed_by_check': False}
