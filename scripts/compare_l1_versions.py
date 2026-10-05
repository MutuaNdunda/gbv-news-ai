#!/usr/bin/env python3
"""Read-only bounded L1 comparison; private observations never go to stdout."""
import argparse
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import Counter
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import statistics
import sys
from time import perf_counter

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from annotations.geography import load_index, resource_identity
from annotations.l1 import evaluate_l1
from annotations.l1_v1 import gazetteer
from annotations.schemas import DEFAULT_CONFIG
from annotations.service import load_article


def compare(records):
    old=replace(DEFAULT_CONFIG,l1_gazetteer='v1')
    times={'v1':[], 'v2':[]}
    rows=[]
    for identifier,article in records:
        results={}
        for version,config in [('v1',old),('v2',DEFAULT_CONFIG)]:
            tick=perf_counter()
            results[version]=evaluate_l1(article,config)
            times[version].append((perf_counter()-tick)*1000)
        row={'article_version_id':identifier}
        for version,result in results.items():
            row[version]={'label':result.label, 'kenya_score':result.evidence['kenya_score'],
                'foreign_score':result.evidence['foreign_score'],'matched_places':result.evidence['kenyan_places']}
        rows.append(row)
    transitions=Counter(row['v1']['label']+' → '+row['v2']['label'] for row in rows)
    summary={'sample_count':len(rows), 'transitions':{a+' → '+b:transitions[a+' → '+b]
        for a in ('kenya','not_kenya','ambiguous') for b in ('kenya','not_kenya','ambiguous')},
        'score_changes':{field:sum(row['v1'][field]!=row['v2'][field] for row in rows)
                        for field in ('kenya_score','foreign_score','matched_places')},
        'mean_scores':{v:{field:statistics.mean(row[v][field] for row in rows) if rows else None
            for field in ('kenya_score','foreign_score')} for v in ('v1','v2')},
        'evaluation_ms':{v:{'mean':round(statistics.mean(t),4) if t else None,
            'median':round(statistics.median(t),4) if t else None} for v,t in times.items()},
        'methods':{'v1':old.method_version('L1'),'v2':DEFAULT_CONFIG.method_version('L1')},
        'gazetteer_sha256':resource_identity(), 'annotation_writes':0}
    return summary, rows


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit',type=int,default=20)
    parser.add_argument('--synthetic',action='store_true',help='Offline engineering examples, not corpus validation')
    parser.add_argument('--output',type=Path,default=ROOT/'data/trials/processed/l1-v1-v2-comparison.json')
    args=parser.parse_args()
    if not 1<=args.limit<=20: parser.error('Limit must be between 1 and 20; full-corpus comparison is intentionally unavailable')
    private_root=(ROOT/'data').resolve()
    if not args.output.resolve().is_relative_to(private_root): parser.error('Output must remain in ignored repository data/')
    loading={}
    gazetteer.cache_clear();load_index.cache_clear();resource_identity.cache_clear()
    for v,loader in [('v1',gazetteer),('v2',load_index)]:
        tick=perf_counter();loader();loading[v]=round((perf_counter()-tick)*1000,3)
    if args.synthetic:
        texts=['Kenya','Nairobi','Paris Britain','No geographic evidence','Karurumo Ward',
            'Kagaari South Ward','Kangema','London Britain','Karen','Airport','Busia',
            'DCI','Murang’a','Nairobi Kampala','Bokoli Market','Kinondo Ward',
            'Kibwezi East Constituency','Lunga Lunga','Rosslyn','Kutus']
        records=[(f'synthetic-{i}',{'article_text':text}) for i,text in enumerate(texts[:args.limit])]
        selection='Synthetic engineering examples; no research labels or corpus claims'
    else:
        from sqlalchemy import select
        from database.models import Article,ArticleVersion,AutomatedAnnotation
        from database.repositories.annotations import current_annotations
        from database.session import create_session_factory
        from storage import GCSStorage
        sessions=create_session_factory()
        current=current_annotations({'L0':DEFAULT_CONFIG.method_version('L0'),'L1':'l1-v1.0'})
        with sessions() as session:
            # Eligible versions with historical v1 results only; bounded stable ordering.
            rows=session.execute(select(ArticleVersion,Article).join(Article,Article.id==ArticleVersion.article_id)
                .where(ArticleVersion.id.in_(select(current.c.article_version_id).where(current.c.layer=='L1')))
                .order_by(ArticleVersion.created_at,ArticleVersion.id).limit(args.limit)).all()
        objects=GCSStorage(); records=[]
        for version,article in rows:
            candidate={'metadata':{k:getattr(article,k) for k in ('source','canonical_url','title','published_at')},
                **{k:getattr(version,k) for k in ('raw_object_uri','processed_object_uri',
                    'processed_object_generation','content_hash','parser_version')}}
            item=load_article(candidate,objects)
            body=item.get('article_text')
            if item['processed_object_missing'] or item['lineage_errors'] or not isinstance(body,str) or hashlib.sha256(body.encode()).hexdigest()!=version.content_hash.lower():
                raise ValueError('Comparison input failed extraction lineage checks')
            records.append((str(version.id),item))
        selection='First current-L0-valid/current-v1-result versions by creation time and UUID; nonrandom smoke sample'
    summary,details=compare(records)
    summary.update(loading_ms=loading,selection=selection,date=datetime.now(ZoneInfo('Africa/Nairobi')).date().isoformat())
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps({'summary':summary,'records':details},indent=2)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':
    try: main()
    except Exception as exc:
        print('Comparison failed: '+type(exc).__name__,file=sys.stderr)
        sys.exit(2)
