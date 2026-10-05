"""Pinned resource integrity, lexical scoring, historical compatibility and UI."""
from dataclasses import replace
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from annotations.geography import GROUPS, load_index, normalize_name, geographic_matches
from annotations.l1 import evaluate_l1
from annotations.l1_v1 import evaluate_l1 as evaluate_v1
from annotations.schemas import DEFAULT_CONFIG
from scripts.build_kenya_gazetteer import build
from tests import test_annotation_pipeline as pipeline


class GazetteerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.data, cls.aliases, _ = load_index()

    def test_deterministic_rebuild_and_computed_counts(self):
        self.assertEqual(build(), self.data)
        expected = dict(counties=47, sub_counties=307, constituencies=290, wards=1448,
                        localities=916, areas=1827, towns=36)
        self.assertEqual(self.data['metadata']['coverage'], expected)
        self.assertEqual({g:len(self.data[g]) for g in GROUPS}, expected)
        self.assertEqual(self.data['metadata']['duplicates_removed']['areas'], 2)

    def test_names_codes_aliases_and_parent_integrity(self):
        counties={x['name'] for x in self.data['counties']}
        cons={(x['name'],x['county']) for x in self.data['constituencies']}
        localities={(normalize_name(x['name']),x['county']) for x in self.data['localities']}
        for g in GROUPS:
            codes=[]
            for x in self.data[g]:
                self.assertTrue(x['name'].strip())
                self.assertTrue(x['aliases'])
                self.assertEqual(x['aliases'], sorted(set(map(normalize_name,x['aliases']))))
                if x['code'] is not None:
                    self.assertIsInstance(x['code'],str)
                    codes.append(x['code'])
                if x['county']: self.assertIn(x['county'],counties)
                if g=='wards': self.assertIn((x['constituency'],x['county']),cons)
                if g=='areas' and x['locality']:
                    self.assertIn((normalize_name(x['locality']),x['county']),localities)
            self.assertEqual(len(codes),len(set(codes)))
        rosslyn=next(x for x in self.data['areas'] if x['name']=='Rosslyn')
        self.assertIsNone(rosslyn['locality'])
        self.assertEqual(rosslyn['source_locality'],'Rosslyn')
        self.assertTrue(rosslyn['ambiguous'])

    def test_all_duplicate_aliases_are_reported(self):
        duplicates={a for a,items in self.aliases.items() if len(items)>1}
        self.assertEqual(duplicates,{x['alias'] for x in self.data['alias_collisions']})
        for collision in self.data['alias_collisions']:
            if collision['ambiguous']:
                self.assertTrue(collision['reasons'])
                self.assertTrue(all(x['ambiguous'] for x in self.aliases[collision['alias']]))

    def test_reference_counts_and_discrepancies_not_silently_merged(self):
        refs=self.data['reference_comparison']
        self.assertEqual(refs['tiga']['wards']['count'],1439)
        self.assertEqual(refs['alvin']['counties']['count'],45)
        self.assertIn(['keroka','','keroka'],refs['alvin']['counties']['reference_only'])
        self.assertNotIn('Keroka',{x['name'] for x in self.data['counties']})

    def test_cached_lookup(self):
        self.assertIs(load_index(),load_index())


class MatchingTests(unittest.TestCase):
    def evaluate(self,text): return evaluate_l1({'article_text':text})

    def test_each_expanded_entity_kind_and_parent(self):
        data,_,_=load_index()
        for group in ('sub_counties','constituencies','wards','localities','areas'):
            kind=GROUPS[group]
            # Choose a unique, unambiguous surface so presentation is unambiguous too.
            entity=next(x for x in data[group] if not x['ambiguous'] and
                len(load_index()[1][normalize_name(x['name'])])==1)
            result=self.evaluate(entity['name']+' '+kind.replace('_',' '))
            self.assertEqual(result.label,'kenya',group)
            observation=result.evidence['kenyan_geographic_evidence'][0]
            self.assertEqual(observation['entity_type'],kind)
            self.assertEqual(observation['county'],entity['county'])
            self.assertEqual(result.evidence['kenya_score'],4.0 if kind=='sub_county' else 3.5 if kind=='ward' else 3.0)

    def test_one_ward_does_not_score_its_parent_hierarchy(self):
        result=self.evaluate('Kagaari South Ward')
        places=result.evidence['kenyan_geographic_evidence']
        self.assertEqual(len(places),1)
        self.assertEqual(places[0]['entity_type'],'ward')
        self.assertEqual(places[0]['county'],'Embu')
        self.assertEqual(places[0]['constituency'],'Runyenjes')
        self.assertEqual(result.evidence['kenya_score'],3.5)
        self.assertEqual(result.evidence['kenyan_counties'],[])

    def test_longest_match_repeat_alias_and_unicode(self):
        result=self.evaluate("MURANG’A Muranga Murang'a")
        self.assertEqual(len(result.evidence['kenyan_geographic_evidence']),1)
        self.assertEqual(result.evidence['kenyan_places'],["Murang'a"])
        self.assertEqual(result.evidence['kenya_score'],3.0)
        self.assertEqual(len(geographic_matches('Nairobi County')),1)
        self.assertEqual(self.evaluate('Karurumofoo Nairobians').label,'ambiguous')

    def test_separately_mentioned_parent_is_independent_evidence(self):
        result=self.evaluate('Kagaari South Ward, Embu')
        self.assertEqual(len(result.evidence['kenyan_geographic_evidence']),2)
        self.assertEqual(result.evidence['kenya_score'],6.5)

    def test_collisions_common_words_surnames_foreign_and_acronyms(self):
        for text in ('Central','Airport','Karen','Busia','London','DCI','KRA','IEBC','ODPP','EACC','KDF'):
            self.assertEqual(self.evaluate(text).label,'ambiguous',text)
        collision=next(x for x in load_index()[0]['alias_collisions'] if 'shared_name_multiple_places' in x['reasons'])
        result=self.evaluate(collision['alias'])
        self.assertEqual(result.label,'ambiguous')
        self.assertTrue(result.evidence['kenyan_geographic_evidence'][0]['candidates'])
        self.assertEqual(self.evaluate('Paris and Britain').label,'not_kenya')
        self.assertEqual(self.evaluate('Karurumo and Kampala').label,'ambiguous')
        self.assertEqual(evaluate_v1({'article_text':'London and Britain'}).label,'not_kenya')

    def test_ordinary_words_do_not_create_strong_place_support(self):
        for term in ('Merit', 'Total', 'Engineer', 'Municipality', 'Banana'):
            result=self.evaluate(term)
            self.assertEqual(result.label,'ambiguous')
            self.assertEqual(result.evidence['kenya_score'],0)

    def test_version_identity_includes_resource_and_config(self):
        legacy=replace(DEFAULT_CONFIG,l1_gazetteer='v1')
        self.assertEqual(legacy.method_version('L1'),'l1-v1.0')
        current=DEFAULT_CONFIG.method_version('L1')
        self.assertTrue(current.startswith('l1-v2.0-'))
        with patch('annotations.geography.resource_identity',return_value='a'*64):
            self.assertNotEqual(current,DEFAULT_CONFIG.method_version('L1'))
        self.assertNotEqual(current,replace(DEFAULT_CONFIG,place_weight=4).method_version('L1'))
        self.assertEqual(legacy.method_version('L0'),DEFAULT_CONFIG.method_version('L0'))
        with self.assertRaises(ValueError): replace(DEFAULT_CONFIG,l1_gazetteer='v3')

    def test_flask_renders_v2_and_legacy_geography_without_article_text(self):
        from app import create_app
        from flask import render_template
        from types import SimpleNamespace
        app=create_app()
        for result in (self.evaluate('Kagaari South Ward'),evaluate_v1({'article_text':'Nairobi'})):
            with app.test_request_context():
                html=render_template('annotations/geography.html',result=result)
            if result.evidence.get('kenyan_geographic_evidence'):
                self.assertIn('Kagaari South',html)
                self.assertIn('Runyenjes',html)
                self.assertIn('Embu',html)
            else: self.assertNotIn('Matched Kenya geography',html)

    def test_full_flask_results_and_history_templates_render_both_versions(self):
        from dataclasses import asdict
        from flask import render_template
        from types import SimpleNamespace
        from uuid import uuid4
        from app import create_app
        from tests.test_annotation_routes import FakeAnnotations
        service=FakeAnnotations()
        results=[]
        for output in (self.evaluate('Kagaari South Ward'),evaluate_v1({'article_text':'Nairobi'})):
            results.append(SimpleNamespace(**asdict(output),id=uuid4(),article_version_id=uuid4(),
                annotation_run_id=uuid4(),created_at='2026-10-04'))
        article=SimpleNamespace(id=uuid4(),article_id=uuid4(),title='Synthetic geography',
            canonical_url='https://example.test/synthetic',source='citizen',publisher_name='Synthetic',
            published_at=None,published_at_raw=None,kenya_relevance=None)
        service.results=lambda *args: ([(result,article) for result in results],2)
        app=create_app({'TESTING':True},{'annotations':service})
        response=app.test_client().get('/annotations/l1')
        self.assertEqual(response.status_code,200)
        self.assertIn('Kagaari South',response.get_data(as_text=True))
        self.assertIn('/annotations/review/',response.get_data(as_text=True))
        with app.test_request_context():
            html=render_template('articles/detail.html',article=article,versions=[],annotations=results)
        self.assertIn('Kagaari South',html)
        self.assertIn('l1-v1.0',html)


class V2PipelineTests(unittest.TestCase):
    def setUp(self):
        self.runner = pipeline.PipelineTests()
        self.runner.setUp()
        self.run_pipeline = self.runner.run_pipeline
        self.repository = self.runner.repository
    def test_v1_history_does_not_satisfy_v2_pending(self):
        old=replace(DEFAULT_CONFIG,l1_gazetteer='v1')
        self.run_pipeline(config=old)
        history=list(self.repository.results)
        summary=self.run_pipeline(layers=['L1'])
        self.assertEqual(summary['success'],1)
        self.assertEqual(self.repository.results[:2],history)
        self.assertEqual(self.repository.results[-1].method_version,DEFAULT_CONFIG.method_version('L1'))
        self.assertEqual(self.repository.results[-1].prerequisite_annotation_id,history[0].id)
        self.assertEqual(self.run_pipeline(layers=['L1'])['requested'],0)
