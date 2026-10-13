"""Immutable private report bundles and checksummed loading, without inference."""
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess

from annotations.l2_training import ROOT, private_output
from annotations.l2_evaluation import METRIC_VERSION

REPORT_ROOT = ROOT / 'data' / 'l2' / 'evaluations'


def serialize(value):
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + '\n'


def checksum(payload):
    return hashlib.sha256(payload).hexdigest()


def reference_digest(pairs):
    return checksum(serialize([{k: r[k] for k in ('member_id', 'annotation_id', 'initial_human_validation_id',
        'final_human_validation_id')} for r in pairs]).encode())


def csv_text(rows, fields):
    output = io.StringIO(newline=''); writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        values = {}
        for key in fields:
            v = row.get(key)
            if isinstance(v, str) and v.lstrip().startswith(('=', '+', '-', '@')):
                v = "'" + v
            values[key] = v
        writer.writerow(values)
    return output.getvalue()


def export_tables(report, pairs):
    files = {}
    if report['classification']:
        classification = report['classification']; classes = []
        for label, row in classification['classes'].items():
            classes.append(dict(label=label, support=row['support'], predicted_support=row['predicted_support'],
                **{k: row[k]['value'] for k in ('precision','recall','f1')}))
        for name, row in classification['aggregates'].items():
            classes.append(dict(label=name, support=classification['binary_evaluable'],
                **{k: row[k]['value'] for k in ('precision','recall','f1')}))
        files['classification.csv'] = csv_text(classes, ['label','support','predicted_support','precision','recall','f1'])
        files['confusion_matrix.csv'] = csv_text([dict(category=k, count=v) for k,v in report['confusion_matrix'].items()], ['category','count'])
        subgroups = []
        for kind, groups in report['subgroups'].items():
            for name, row in groups.items():
                subgroups.append(dict(kind=kind, subgroup=name, **{k: row[k] for k in
                    ('sample_size','human_gbv','human_not_gbv','model_gbv','model_not_gbv','abstentions','binary_evaluable')},
                    **{k: v['value'] for k,v in row['metric_details'].items()}, warning=row['warning']))
        files['subgroups.csv'] = csv_text(subgroups, ['kind','subgroup','sample_size','human_gbv','human_not_gbv',
            'model_gbv','model_not_gbv','abstentions','binary_evaluable','precision','recall','f1','macro_f1','accuracy','warning'])
    # No headline, article body, reasons, victim details or reviewer identities in defaults.
    files['errors.csv'] = csv_text(pairs, ['member_id','source','language','model_label','gbv_probability',
        'human_label','error_category','model_version','guideline_version','evidence_basis'])
    return files


def persist_report(output, batch, report, pairs):
    output = private_output(output)
    if not output.is_relative_to(ROOT / 'data') or output.exists():
        raise ValueError('Use a new private output directory under ignored data/.')
    payload = ''.join(json.dumps(r,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n' for r in pairs)
    report['records_sha256'] = checksum(payload.encode())
    report['reference_pointers_sha256'] = reference_digest(pairs)
    try:
        commit = subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = 'unavailable'
    report['code_commit'] = commit
    report['implementation_sha256'] = {name:checksum((ROOT/name).read_bytes()) for name in (
        'annotations/l2_evaluation.py','annotations/validation_batches.py','annotations/reference_quality.py',
        'annotations/evaluation_reports.py','scripts/evaluate_l2_validation.py')}
    files = dict(export_tables(report,pairs), **{'evaluation_pairs.jsonl':payload, 'evaluation_report.json':serialize(report)})
    manifest = dict(batch_id=str(batch.id), batch_name=batch.name,
        evaluation_pairs_sha256=report['records_sha256'],
        evaluation_report_sha256=checksum(files['evaluation_report.json'].encode()),
        metric_definition_version=METRIC_VERSION, files_sha256={k:checksum(v.encode()) for k,v in files.items()})
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    for name, data in dict(files, **{'manifest.json':serialize(manifest)}).items():
        path = output/name; path.write_text(data); path.chmod(0o600)
    # Actual calculation invocation time is separate from deterministic mathematical evidence.
    invocation = serialize(dict(calculated_at=datetime.now(timezone.utc).isoformat(), code_commit=commit,
        report_sha256=manifest['evaluation_report_sha256'], metric_definition_version=METRIC_VERSION))
    (output/'invocation.json').write_text(invocation); (output/'invocation.json').chmod(0o600)
    (output/'invocation_manifest.json').write_text(serialize({'invocation_sha256':checksum(invocation.encode())}))
    (output/'invocation_manifest.json').chmod(0o600)
    return manifest


def load_bundle(directory, batch, members, root=REPORT_ROOT):
    try:
        return _load_bundle(directory, batch, members, root)
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError('Malformed private evaluation bundle; regenerate into a new directory.') from exc


def _load_bundle(directory, batch, members, root):
    """Never accept path traversal/symlinks or evidence from another completed instrument."""
    root, path = Path(root).resolve(), Path(directory)
    if any(p.is_symlink() for p in [path, *path.parents]) or not path.resolve().is_relative_to(root):
        raise ValueError('Unsafe report path.')
    if batch.status != 'completed':
        raise ValueError('Evaluation pending — human reference batch has not been completed.')
    if (path/'manifest.json').is_symlink():
        raise ValueError('Unsafe manifest path.')
    manifest = json.loads((path/'manifest.json').read_text())
    allowed = {'evaluation_pairs.jsonl','evaluation_report.json','classification.csv','confusion_matrix.csv','subgroups.csv','errors.csv'}
    for name, digest in manifest.get('files_sha256', {}).items():
        if name not in allowed or (path/name).is_symlink() or checksum((path/name).read_bytes()) != digest:
            raise ValueError('Private evaluation file checksum mismatch.')
    if not {'evaluation_pairs.jsonl','evaluation_report.json'} <= set(manifest.get('files_sha256', {})):
        raise ValueError('Legacy report: regenerate with the shared v2 evaluator into a new directory.')
    report = json.loads((path/'evaluation_report.json').read_text())
    pairs = [json.loads(line) for line in (path/'evaluation_pairs.jsonl').read_text().splitlines()]
    from annotations.validation_batches import membership_digest
    snapshot = [dict(article_id=m.article_id,id=m.article_version_id,annotation_id=m.automated_annotation_id,
        content_hash=m.content_hash,source=m.source,language=m.language,stratum=m.sampling_stratum) for m in members]
    if len(members) != batch.requested_size or membership_digest(snapshot) != batch.configuration.get('membership_sha256'):
        raise ValueError('Frozen membership digest mismatch.')
    if (report.get('metric_definition_version') != METRIC_VERSION or report.get('batch_id') != str(batch.id)
        or manifest.get('batch_id') != str(batch.id) or report.get('model_version') != batch.model_version
        or report.get('method_version') != batch.model_method_version or report.get('purpose') != batch.purpose
        or report.get('guideline_version') != batch.guideline_version
        or report.get('configuration') != batch.configuration
        or report.get('records_sha256') != manifest['files_sha256']['evaluation_pairs.jsonl']
        or manifest.get('evaluation_pairs_sha256') != report.get('records_sha256')
        or manifest.get('evaluation_report_sha256') != manifest['files_sha256']['evaluation_report.json']):
        raise ValueError('Report/model/batch/codebook identity mismatch.')
    live = [dict(member_id=str(m.id), annotation_id=str(m.automated_annotation_id),
        initial_human_validation_id=str(m.initial_human_validation_id), final_human_validation_id=str(m.final_human_validation_id))
        for m in members]
    if len(pairs) != len(members) or reference_digest(live) != report.get('reference_pointers_sha256'):
        raise ValueError('Accepted reference pointers differ from the private report.')
    if any(r.get('content_hash') != m.content_hash or r['article_id'] != str(m.article_id)
           or r['article_version_id'] != str(m.article_version_id) for r,m in zip(pairs,members)):
        raise ValueError('Private report extraction lineage mismatch.')
    if batch.purpose == 'final_test' and not report.get('final_experiment_released'):
        raise ValueError('Final-test feedback remains sealed until explicit CLI release.')
    quality=report.get('reference_quality') or {}
    if batch.purpose != 'diagnostic' and (not batch.protect_from_training
        or not quality.get('training_exclusion_verified') or quality.get('issues')
        or quality.get('batch_id') != str(batch.id)
        or quality.get('membership_sha256') != batch.configuration.get('membership_sha256')):
        raise ValueError('Private report lacks verified reference/training integrity evidence.')
    for name in ('invocation.json','invocation_manifest.json'):
        if (path/name).is_symlink(): raise ValueError('Unsafe calculation-time path.')
    invocation_manifest=json.loads((path/'invocation_manifest.json').read_text())
    if checksum((path/'invocation.json').read_bytes()) != invocation_manifest.get('invocation_sha256'):
        raise ValueError('Calculation-time checksum mismatch.')
    invocation=json.loads((path/'invocation.json').read_text())
    if invocation.get('report_sha256') != manifest['evaluation_report_sha256']:
        raise ValueError('Calculation-time report identity mismatch.')
    return dict(report=report, pairs=pairs, manifest=manifest, directory=path,
                artifact_id=manifest['evaluation_report_sha256'], invocation=invocation)
