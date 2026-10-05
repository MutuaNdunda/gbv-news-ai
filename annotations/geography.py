"""Shared literal normalization and cached token-trie geography matching."""
from collections import defaultdict
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import unicodedata

RESOURCE = Path(__file__).parent / 'resources/kenya_v2.json'
GROUPS = {'counties': 'county', 'sub_counties': 'sub_county',
          'constituencies': 'constituency', 'wards': 'ward',
          'localities': 'locality', 'areas': 'area', 'towns': 'town'}


def normalize_name(value):
    value = unicodedata.normalize('NFKC', value).casefold()
    value = value.translate(str.maketrans({'’': "'", '‘': "'", '–': '-', '—': '-', '‑': '-'}))
    return re.sub(r'\s+', ' ', value.replace("'", '').replace('-', ' ')).strip()


@lru_cache(maxsize=1)
def resource_identity():
    return hashlib.sha256(RESOURCE.read_bytes()).hexdigest()


@lru_cache(maxsize=1)
def load_index():
    data = json.loads(RESOURCE.read_text(encoding='utf-8'))
    aliases = defaultdict(list)
    for group, kind in GROUPS.items():
        for item in data[group]:
            entity = dict(item, entity_type=kind)
            for alias in {normalize_name(item['name']), *item['aliases']}:
                aliases[alias].append(entity)
    trie = {}
    for alias, entities in sorted(aliases.items()):
        node = trie
        for token in re.findall(r'\w+|[^\w\s]', alias):
            node = node.setdefault(token, {})
        node[None] = (alias, entities)
    return data, dict(aliases), trie


def geographic_matches(text):
    """Longest non-overlapping lexical matches; hierarchy never adds observations.

    Return all candidate entities when a surface has several interpretations.
    A type suffix selects presentation only; it does not cure lexical ambiguity.
    """
    data, aliases, trie = load_index()
    tokens = re.findall(r'\w+|[^\w\s]', normalize_name(text))
    observations = []
    i = 0
    seen = set()
    priority = {'county': 0, 'town': 1, 'constituency': 2, 'sub_county': 3,
                'ward': 4, 'locality': 5, 'area': 6}
    suffixes = {'county': 'county', 'constituency': 'constituency', 'ward': 'ward',
                'locality': 'locality', 'area': 'area'}
    while i < len(tokens):
        node, j, longest = trie, i, None
        while j < len(tokens) and tokens[j] in node:
            node = node[tokens[j]]
            j += 1
            if None in node:
                longest = (j, *node[None])
        if longest is None:
            i += 1
            continue
        end, alias, candidates = longest
        suffix = suffixes.get(tokens[end] if end < len(tokens) else '')
        if tokens[end:end+2] == ['sub', 'county']:
            suffix = 'sub_county'
        selected = sorted(candidates, key=lambda x: (x['entity_type'] != suffix,
                          priority[x['entity_type']], x['county'] or '', x['name']))[0]
        key = normalize_name(selected['name'])
        if key not in seen:
            seen.add(key)
            reasons = sorted({reason for item in candidates for reason in item['ambiguity_reasons']})
            observations.append({'matched_term': alias, 'canonical_name': selected['name'],
                'entity_type': selected['entity_type'], 'county': selected['county'],
                'sub_county': selected.get('sub_county'), 'constituency': selected.get('constituency'),
                'locality': selected.get('locality'), 'code': selected['code'], 'source': selected['source'],
                'ambiguous': bool(reasons), 'ambiguity_reasons': reasons,
                'candidates': [{k: item.get(k) for k in ('entity_type', 'name', 'county', 'constituency', 'code')}
                               for item in candidates] if len(candidates) > 1 else []})
        i = end
    return observations
