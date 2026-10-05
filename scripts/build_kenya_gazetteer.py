#!/usr/bin/env python3
"""Offline, hash-checked, deterministic build from pinned upstream name datasets."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from annotations.geography import GROUPS, normalize_name

UPSTREAM = ROOT / 'annotations/resources/upstream'
PRIMARY = 'davidamunga/kenya-locations'
# Explicit lexical risk policy; no automatic disambiguation from publisher identity.
COMMON = set('airport township central north south east west hospital market town school village stage university pipeline junction industrial park garden springs island railway station racecourse riverside mountain view landless highrise huruma karen hardy merit total engineer municipality banana annex blankets carwash deliverance flamingo hunters impala ravine turbo major minor marine pioneer prestige satellite service scheme estate estates royal valley division district industrial commercial residential office offices factory college police prison barracks bridge beach sports complex mosque church temple stadium post blue green red white yellow golden happy hope peace joy spring summer king queen champion globe pleasant globe cinema junction northlands highlands grassland plains bond oasis embassy'.split())
SURNAMES = {'wanjiru', 'kamau', 'otieno', 'onyango', 'mwangi', 'mutua', 'kagwe', 'maina', 'kimathi', 'barnabas', 'zimmerman'}
FOREIGN_SHARED = {'california', 'bangladesh', 'jerusalem', 'jericho', 'hindi', 'tudor'}


def build():
    manifest = json.loads((UPSTREAM/'manifest.json').read_text())
    for source in manifest['sources']:
        for name, digest in source['files'].items():
            if hashlib.sha256((UPSTREAM/source['directory']/name).read_bytes()).hexdigest() != digest:
                raise ValueError(f'Upstream checksum mismatch: {source["directory"]}/{name}')
    read = lambda directory, name: json.loads((UPSTREAM/directory/name).read_text())
    old = json.loads((ROOT/'annotations/resources/kenya_v1.json').read_text())
    county_names = {normalize_name(n): n for n in old['counties']}
    county_names.update({normalize_name(a): n for a, n in old['county_variants'].items()})
    county_names.update({normalize_name(a): n for a,n in {"Elegeyo Marakwet":"Elgeyo Marakwet", "Nairobi City":"Nairobi"}.items()})
    canonical_county = lambda n: county_names[normalize_name(n)]
    raw = {group: read('david', filename) for group, filename in {
        'counties':'counties.json', 'sub_counties':'sub-counties.json', 'constituencies':'constituencies.json',
        'wards':'wards.json', 'localities':'locality.json', 'areas':'area.json'}.items()}
    constituencies = {normalize_name(x['name']): x for x in raw['constituencies']}
    if len(constituencies) != len(raw['constituencies']):
        raise ValueError('Nonunique constituency names require explicit resolution')
    output = {}
    duplicates = {}
    for group, items in raw.items():
        result = {}
        for x in items:
            name = canonical_county(x['name']) if group == 'counties' else x['name'].strip().replace('’', "'")
            parent = constituencies[normalize_name(x['constituency'])] if group == 'wards' else None
            county = name if group == 'counties' else canonical_county(parent['county'] if parent else x['county'])
            item = dict(name=name, county=county, code=str(x['code']) if x.get('code') else None,
                        aliases=sorted({normalize_name(name), normalize_name(x['name'])}), source=PRIMARY,
                        ambiguity_reasons=[])
            if group == 'wards': item['constituency'] = parent['name']
            if group == 'constituencies': item['constituency'] = name
            if group == 'sub_counties': item['sub_county'] = name
            if group == 'areas': item['locality'] = x['locality']
            if group == 'counties':
                item['aliases'] = sorted(set(item['aliases']) | {normalize_name(a) for a,n in old['county_variants'].items() if n==name})
            key = (normalize_name(name), county, item.get('constituency'), item.get('locality'))
            if key in result:
                if result[key]['code'] != item['code']:
                    raise ValueError(f'Conflicting duplicate code: {key}')
                result[key]['aliases'] = sorted(set(result[key]['aliases']) | set(item['aliases']))
                result[key]['name'] = min(result[key]['name'], item['name'])
            else:
                result[key] = item
        output[group] = sorted(result.values(), key=lambda x:(x['name'],x['county'],x.get('locality','')))
        duplicates[group] = len(items)-len(result)
    # Retain established towns, without inventing county parents.
    output['towns'] = [dict(name=n, county=None, code=None,
        aliases=sorted({normalize_name(n)} | {normalize_name(a) for a,v in old['place_variants'].items() if v==n}),
        source='repository/kenya_v1.json', ambiguity_reasons=[]) for n in sorted(old['towns'])]
    county_set={x['name'] for x in output['counties']}
    locality_set={(normalize_name(x['name']),x['county']) for x in output['localities']}
    for group, items in output.items():
        codes = [x['code'] for x in items if x['code']]
        if len(codes)!=len(set(codes)): raise ValueError(f'Duplicate codes in {group}')
        for x in items:
            if x['county'] and x['county'] not in county_set: raise ValueError('Invalid county')
            if group=='areas' and (normalize_name(x['locality']),x['county']) not in locality_set:
                x['source_locality'] = x['locality']
                x['locality'] = None
                x['ambiguity_reasons'].append('unresolved_upstream_locality_parent')
    aliases=defaultdict(list)
    for group,items in output.items():
        for x in items:
            for alias in x['aliases']: aliases[alias].append((group,x))
    collisions=[]
    for alias,items in sorted(aliases.items()):
        counties={x['county'] for _,x in items if x['county']}
        ward_parents={x.get('constituency') for g,x in items if g=='wards'}
        area_parents={(x['county'],x.get('locality')) for g,x in items if g=='areas'}
        reasons=[]
        if len(counties)>1 or len(ward_parents)>1 or len(area_parents)>1: reasons.append('shared_name_multiple_places')
        if alias in {normalize_name(n) for n in old['ambiguous_places']}: reasons.append('legacy_cross_border_ethnic_or_foreign_name')
        if alias in COMMON: reasons.append('ordinary_word_or_person_name')
        if alias in FOREIGN_SHARED | {normalize_name(n) for n in old['foreign_places']}: reasons.append('kenyan_and_foreign_place')
        if alias in SURNAMES: reasons.append('possible_surname')
        if len(alias)<4: reasons.append('short_ambiguous_name')
        for _,x in items: x['ambiguity_reasons'] = sorted(set(x['ambiguity_reasons'])|set(reasons))
        if len(items)>1:
            collisions.append(dict(alias=alias,ambiguous=bool(reasons),reasons=reasons,
                candidates=[dict(entity_type=GROUPS[g],name=x['name'],county=x['county'],code=x['code']) for g,x in items]))
    # Compare normalized county/constituency/ward tuples; references never silently repair primary data.
    primary_sets={g:set() for g in ('counties','constituencies','wards')}
    for g in primary_sets:
        primary_sets[g]={tuple(normalize_name(x.get(k) or '') for k in ('county','constituency','name')) for x in output[g]}
    references={}
    for directory in ('tiga','alvin'):
        sets={g:set() for g in primary_sets}
        if directory=='tiga':
            for g,field in [('counties','county'),('constituencies','constituency'),('wards','ward')]:
                for x in read(directory,g+'.json'):
                    c=county_names.get(normalize_name(x['county_name'] or ''), x['county_name'] or '')
                    sets[g].add((normalize_name(c),normalize_name(x.get('constituency_name') or '') if g!='counties' else '',normalize_name(c if g=='counties' else x[field+'_name'])))
        else:
            for c,cons in read(directory,'Kenya-Counties-SubCounties-and-Wards.json').items():
                c=county_names.get(normalize_name(c), c)
                sets['counties'].add((normalize_name(c),'',normalize_name(c)))
                for con,wards in cons.items():
                    sets['constituencies'].add((normalize_name(c),normalize_name(con),normalize_name(con)))
                    for w in wards: sets['wards'].add((normalize_name(c),normalize_name(con),normalize_name(w)))
        references[directory]={g:dict(count=len(sets[g]),primary_only=sorted(primary_sets[g]-sets[g]),reference_only=sorted(sets[g]-primary_sets[g])) for g in sets}
    for items in output.values():
        for x in items: x['ambiguous']=bool(x['ambiguity_reasons'])
    coverage={g:len(items) for g,items in output.items()}
    output['metadata']=dict(version='kenya-gazetteer-v2.0',build_date=manifest['build_date'],sources=manifest['sources'],
        coverage=coverage,duplicates_removed=duplicates,code_policy='Upstream codes preserved as strings; not independently certified official.',
        build_script='scripts/build_kenya_gazetteer.py',normalization='NFKC, casefold, apostrophe removal, dash/space equivalence; exact literal matching')
    output['country']=dict(name='Kenya',aliases=['kenya'],demonyms=old['country_terms'][1:])
    for field in ('country_terms','institutions','ambiguous_institutions','admin_terms','foreign_places'):
        output[field]=old[field]
    output['ambiguous_places']=sorted({x['name'] for g in GROUPS for x in output[g] if x['ambiguous']})
    output['alias_collisions']=collisions
    output['reference_comparison']=references
    return json.loads(json.dumps(output))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    path=ROOT/'annotations/resources/kenya_v2.json'
    content=json.dumps(build(),ensure_ascii=False,indent=2,sort_keys=True)+'\n'
    if args.check:
        if path.read_text()!=content: raise SystemExit('Gazetteer differs from deterministic rebuild')
    else: path.write_text(content,encoding='utf-8')
    print('Gazetteer '+('verified' if args.check else 'built'))

if __name__=='__main__': main()
