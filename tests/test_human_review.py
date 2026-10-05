"""Execute review UI, storage, security and cohort queries on synthetic SQLite data."""
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from bs4 import BeautifulSoup
from sqlalchemy import JSON, MetaData, create_engine, event, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import sessionmaker

from annotations.l1 import evaluate_l1
from annotations.schemas import DEFAULT_CONFIG
from annotations.validation import ReviewConflict
from app import create_app
from app.services.annotation_service import AnnotationService
from app.services.article_service import ArticleService
from database.models import Base, Article, ArticleVersion, AnnotationRun, AutomatedAnnotation, HumanValidation
from database.repositories.human_validations import latest_validations


class ReviewFixture(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite://')
        @event.listens_for(self.engine,'connect')
        def configure(connection, record):
            connection.execute("ATTACH DATABASE ':memory:' AS public")
            connection.execute('PRAGMA foreign_keys=ON')
        metadata=MetaData()
        for original in Base.metadata.sorted_tables:
            table=original.to_metadata(metadata)
            for column in table.columns:
                if isinstance(column.type,JSONB): column.type=JSON()
                if column.server_default is not None and str(column.server_default.arg) in ('now()','gen_random_uuid()'):
                    column.server_default=None
        metadata.create_all(self.engine)
        self.sessions=sessionmaker(bind=self.engine,expire_on_commit=False)
        self.now=datetime(2026,10,4,tzinfo=timezone.utc)
        self.run=AnnotationRun(id=uuid4(),requested_layers=['L0','L1'],method_versions={},configuration={},
            status='completed',trigger_type='cli',created_at=self.now,started_at=self.now)
        self.records={}; self.annotations=[]; self.articles=[]
        with self.sessions.begin() as session:
            session.add(self.run);session.flush()
            for index, (l0,label,source) in enumerate([
                ('valid','kenya','citizen'),('valid','not_kenya','citizen'),
                ('valid','ambiguous','citizen'),('valid','ambiguous','citizen'),
                ('valid','ambiguous','star'),('needs_review',None,'citizen'),
                ('needs_review',None,'citizen'),('invalid',None,'citizen')]):
                tick=self.now+timedelta(seconds=index)
                body=f'Synthetic article {index}: community education reporting. ' * 10
                if index==2: body += '<script>window.reviewLeak="private-text"</script>'
                digest=hashlib.sha256(body.encode()).hexdigest()
                url='https://citizen.digital/news/synthetic-n1' if source=='citizen' else 'https://www.the-star.co.ke/news/synthetic'
                article=Article(id=uuid4(),article_id=f'synthetic-{index}',source=source,title=f'Synthetic article {index}',
                    canonical_url=url+str(index),published_at=None if index==5 else self.now,
                    published_at_raw=None,kenya_relevance='needs_review',publication_date_needs_review=index==5,
                    first_seen_at=tick,created_at=tick,updated_at=tick)
                version=ArticleVersion(id=uuid4(),article_id=article.id,collection_run_id=None,
                    parser_version='synthetic-v1',content_hash=digest,scraped_at=tick,
                    raw_object_uri=f'gs://raw/{index}.html',processed_object_uri=f'gs://processed/{index}.json',
                    processed_object_generation='123',processing_status='indexed',created_at=tick)
                session.add(article);session.flush()
                session.add(version);session.flush()
                self.articles.append(article)
                self.records[f'{index}.json']={'source':source,'canonical_url':article.canonical_url,
                    'title':article.title,'published_at':article.published_at,'article_text':body,
                    'content_hash':digest,'parser_version':version.parser_version}
                reasons=['missing_published_at'] if index==5 else ['body_too_short'] if index==6 else []
                machine=AutomatedAnnotation(id=uuid4(),article_id=article.id,article_version_id=version.id,
                    annotation_run_id=self.run.id,layer='L0',label=l0,method_name='extraction_quality_rules',
                    method_version=DEFAULT_CONFIG.method_version('L0'),created_at=tick,
                    evidence={'body_chars':100 if index==6 else len(body),'body_words':20 if index==6 else 70,
                        'minimum_body_chars':200,'minimum_body_words':35,'publication_date_flagged':index==5,
                        'hard_failures':[],'soft_anomalies':reasons},reason_codes=reasons)
                session.add(machine);session.flush();self.annotations.append(machine)
                if label:
                    evidence=evaluate_l1({'article_text':'Kagaari South Ward'}).evidence if index==0 else {
                        'kenya_score':0,'foreign_score':3 if index==1 else 0,'net_score':-3 if index==1 else 0,
                        'kenya_mentions':0,'kenyan_places':[],'kenyan_counties':[],
                        'kenyan_institutions':[],'ambiguous_places':[],'ambiguous_institutions':[],
                        'foreign_places':['Paris'] if index==1 else [],'admin_terms':[],
                        'gazetteer_version':'kenya-gazetteer-v2.0'}
                    l1=AutomatedAnnotation(id=uuid4(),article_id=article.id,article_version_id=version.id,
                        annotation_run_id=self.run.id,prerequisite_annotation_id=machine.id,
                        layer='L1',label=label,confidence=.6,method_name='kenya_relevance_hybrid',
                        method_version=DEFAULT_CONFIG.method_version('L1'),created_at=tick,evidence=evidence,reason_codes=[])
                    session.add(l1);session.flush();self.annotations.append(l1)
            old=AutomatedAnnotation(id=uuid4(),article_id=self.annotations[1].article_id,
                article_version_id=self.annotations[1].article_version_id,annotation_run_id=self.run.id,
                prerequisite_annotation_id=self.annotations[0].id,layer='L1',label='kenya',confidence=.6,
                method_name='kenya_relevance_hybrid',method_version='l1-v1.0',created_at=self.now-timedelta(days=1),
                evidence={'kenyan_places':['Nairobi'],'kenyan_institutions':[],'foreign_places':[],
                          'gazetteer_version':'kenya-gazetteer-v1.0'},reason_codes=[])
            session.add(old);self.historical=old
        self.objects=Mock(buckets={'processed':'processed'})
        self.objects.read_json.side_effect=lambda role,key,generation=None:self.records[key]
        self.service=AnnotationService(self.sessions,self.objects)
        self.app=create_app({'TESTING':True,'PER_PAGE':1,'SECRET_KEY':'s'*40,
            'HUMAN_REVIEW_ENABLED':True,'HUMAN_REVIEW_TOKEN':'r'*40,
            'HUMAN_REVIEWER_ID':'configured-researcher','HUMAN_REVIEW_GUIDELINE_VERSION':'synthetic-test-guide'},
            {'annotations':self.service,'articles':ArticleService(self.sessions)})
        self.client=self.app.test_client()

    def tearDown(self): self.engine.dispose()

    def matching(self,layer,label):
        return [x for x in self.annotations if x.layer==layer and x.label==label]

    def url(self,annotation,query=''):
        return f'/annotations/review/{annotation.id}'+query

    def csrf(self):
        with self.client.session_transaction() as session: return session['human_review_csrf']

    def unlock(self,annotation,query=''):
        url=self.url(annotation,query)
        response=self.client.get(url)
        self.assertEqual(response.status_code,200)
        response=self.client.post(url,data={'action':'unlock','csrf_token':self.csrf(),'review_token':'r'*40})
        self.assertEqual(response.status_code,303)
        self.client.get(response.location)

    def save(self,annotation,decision='confirmed',human_label='',expected='',query='',action='save',**kwargs):
        return self.client.post(self.url(annotation,query),data={'action':action,'csrf_token':self.csrf(),
            'decision':decision,'human_label':human_label,'expected_current_id':expected,
            'error_category':'','reason':'','notes':'',**kwargs})

    def count(self):
        with self.sessions() as session: return session.scalar(select(func.count()).select_from(HumanValidation))


class HumanReviewTests(ReviewFixture):
    def test_all_dashboard_machine_counts_and_totals_link_correctly(self):
        response=self.client.get('/annotations');self.assertEqual(response.status_code,200)
        soup=BeautifulSoup(response.data,'html.parser')
        for layer,labels in [('l0',['valid','needs_review','invalid']),('l1',['kenya','not_kenya','ambiguous'])]:
            self.assertTrue(soup.select(f'a[href="/annotations/{layer}"]'))
            for label in labels:
                self.assertTrue(soup.select(f'a[href="/annotations/{layer}?label={label}"]'))
        self.assertIn(DEFAULT_CONFIG.method_version('L1'),response.get_data(as_text=True))
        self.objects.read_json.assert_not_called()

    def test_filtered_lists_paginate_show_title_and_status_and_preserve_context(self):
        response=self.client.get('/annotations/l1?label=ambiguous&source=citizen')
        soup=BeautifulSoup(response.data,'html.parser');rows=soup.select('tr.annotation-row')
        self.assertEqual(len(rows),1)
        self.assertIn('Synthetic article 3',rows[0].get_text())
        self.assertNotIn('Synthetic article 4',rows[0].get_text())
        self.assertIn('Not reviewed',rows[0].get_text())
        query=parse_qs(urlsplit(rows[0].select_one('a')['href']).query)
        self.assertEqual(query['label'],['ambiguous']);self.assertEqual(query['source'],['citizen'])
        self.assertTrue(soup.select('a[href*="page=2"]'))
        page2=self.client.get('/annotations/l1?label=ambiguous&source=citizen&page=2')
        self.assertIn('Synthetic article 2',page2.get_data(as_text=True))
        self.objects.read_json.assert_not_called()

    def test_invalid_filters_rejected_and_all_labels_reviewable(self):
        for path in ('/annotations/l0?label=kenya','/annotations/l1?label=valid',
                     '/annotations/l1?label=unknown','/annotations/l0?source=unknown',
                     '/annotations/l1?review_status=unknown'):
            self.assertEqual(self.client.get(path).status_code,400,path)
        for annotation in self.annotations:
            self.assertEqual(self.client.get(self.url(annotation)).status_code,200)
        self.assertEqual(self.client.get(f'/annotations/review/{uuid4()}').status_code,404)

    def test_locked_review_has_no_text_or_storage_reads(self):
        annotation=self.matching('L1','ambiguous')[0]
        response=self.client.get(self.url(annotation));self.assertEqual(response.status_code,200)
        self.assertNotIn('private-text',response.get_data(as_text=True))
        self.objects.read_json.assert_not_called()
        self.assertEqual(response.headers['Cache-Control'],'private, no-store')

    def test_body_is_escaped_pinned_and_two_way_navigation_works(self):
        annotation=self.matching('L1','ambiguous')[0]
        self.unlock(annotation)
        response=self.client.get(self.url(annotation));html=response.get_data(as_text=True)
        self.assertIn('&lt;script&gt;',html);self.assertNotIn('<script>window.reviewLeak',html)
        self.assertIn(f'/articles/{annotation.article_id}',html)
        self.objects.read_json.assert_called_with('processed','2.json',generation='123')
        article=self.client.get(f'/articles/{annotation.article_id}')
        self.assertIn(self.url(annotation),article.get_data(as_text=True))

    def test_l0_missing_date_and_short_body_and_l1_evidence_render(self):
        for annotation in self.matching('L0','needs_review'):
            self.unlock(annotation)
            html=self.client.get(self.url(annotation)).get_data(as_text=True)
            self.assertIn(annotation.reason_codes[0],html)
            self.assertIn('Minimum characters',html)
            if 'missing_published_at' in annotation.reason_codes:self.assertIn('Date unavailable',html)
            else:self.assertIn('100',html)
        annotation=self.matching('L1','kenya')[0]
        self.unlock(annotation)
        html=self.client.get(self.url(annotation)).get_data(as_text=True)
        for text in ('Kagaari South','Runyenjes','Embu','Kenya score','Foreign score','Gazetteer version'):
            self.assertIn(text,html)
        self.unlock(self.historical)
        self.assertIn('kenya-gazetteer-v1.0',self.client.get(self.url(self.historical)).get_data(as_text=True))

    def test_confirm_is_separate_server_attributed_and_updates_summary(self):
        annotation=self.matching('L1','kenya')[0]
        self.unlock(annotation)
        response=self.save(annotation,reviewer_identity='forged',guideline_version='forged')
        self.assertEqual(response.status_code,303);self.assertEqual(self.count(),1)
        with self.sessions() as session:
            machine=session.get(AutomatedAnnotation,annotation.id)
            validation=session.scalar(select(HumanValidation))
            self.assertEqual(machine.label,'kenya')
            self.assertEqual(validation.human_label,'kenya')
            self.assertEqual(validation.automated_annotation_id,annotation.id)
            self.assertEqual(validation.article_version_id,annotation.article_version_id)
            self.assertEqual(validation.reviewer_identity,'configured-researcher')
            self.assertEqual(validation.guideline_version,'synthetic-test-guide')
        html=self.client.get('/annotations/l1?label=kenya').get_data(as_text=True)
        self.assertIn('Reviewed — confirmed',html)
        summary=self.service.overview()['human_review']
        self.assertEqual(summary['counts']['L1']['confirmed'],1)
        self.assertEqual(summary['counts']['L1']['not_reviewed'],4)
        self.assertEqual(self.client.get('/annotations/l1?review_status=confirmed').status_code,200)

    def test_correction_requires_reason_and_preserves_machine_evidence(self):
        annotation=self.matching('L0','needs_review')[0]
        self.unlock(annotation)
        response=self.save(annotation,'corrected','valid',error_category='publication_date',reason='Synthetic source date verified')
        self.assertEqual(response.status_code,303)
        with self.sessions() as session:
            machine=session.get(AutomatedAnnotation,annotation.id)
            review=session.scalar(select(HumanValidation))
            self.assertEqual(machine.label,'needs_review')
            self.assertEqual(machine.reason_codes,['missing_published_at'])
            self.assertEqual(review.human_label,'valid')
        self.assertEqual(self.service.overview()['human_review']['progress']['L0']['reviewed'],1)

    def test_invalid_cross_layer_labels_decisions_and_missing_reasons_do_not_write(self):
        annotation=self.matching('L1','kenya')[0];self.unlock(annotation)
        for decision,label,extra in [('confirmed','valid',{}),('corrected','kenya',{}),
                ('bad','ambiguous',{}),('corrected','not_kenya',{}),
                ('unable_to_determine','kenya',{}),('needs_adjudication','valid',{}),
                ('corrected','ambiguous',{'error_category':'bad','reason':'x'}),
                ('confirmed','kenya',{'notes':'x'*4001})]:
            response=self.save(annotation,decision,label,**extra)
            self.assertEqual(response.status_code,422,(decision,label))
        self.assertEqual(self.count(),0)

    def test_unresolved_decisions_preserve_null_human_label(self):
        for decision in ('unable_to_determine','needs_adjudication'):
            annotation=self.matching('L1','ambiguous')[0 if decision=='unable_to_determine' else 1]
            self.unlock(annotation);self.assertEqual(self.save(annotation,decision).status_code,303)
        with self.sessions() as session:
            reviews=session.scalars(select(HumanValidation)).all()
            self.assertEqual({r.review_decision for r in reviews},{'unable_to_determine','needs_adjudication'})
            self.assertTrue(all(r.human_label is None for r in reviews))

    def test_csrf_token_authorization_and_replay_enforced(self):
        annotation=self.matching('L1','kenya')[0]
        self.client.get(self.url(annotation))
        response=self.client.post(self.url(annotation),data={'action':'unlock','review_token':'r'*40,'csrf_token':'bad'})
        self.assertEqual(response.status_code,403)
        response=self.client.post(self.url(annotation),data={'action':'unlock','review_token':'bad','csrf_token':self.csrf()})
        self.assertEqual(response.status_code,403)
        self.assertEqual(self.save(annotation).status_code,403)
        self.unlock(annotation)
        csrf=self.csrf();self.assertEqual(self.save(annotation).status_code,303)
        response=self.client.post(self.url(annotation),data={'action':'save','decision':'confirmed','csrf_token':csrf})
        self.assertEqual(response.status_code,403);self.assertEqual(self.count(),1)

    def test_revisions_preserve_history_latest_status_and_reject_stale_expected_id(self):
        annotation=self.matching('L1','kenya')[0];self.unlock(annotation)
        self.assertEqual(self.save(annotation).status_code,303)
        first=self.service.reviews.history(annotation.id)[0]
        self.client.get(self.url(annotation))
        response=self.save(annotation,'corrected','ambiguous',expected=str(first.id),
                           error_category='ambiguity',reason='Synthetic uncertainty')
        self.assertEqual(response.status_code,303)
        history=self.service.reviews.history(annotation.id)
        self.assertEqual(len(history),2);self.assertEqual(history[0].supersedes_validation_id,first.id)
        self.assertEqual(history[1].review_decision,'confirmed')
        self.assertEqual(self.service.reviews.statuses([annotation.id])[annotation.id],'corrected')
        self.client.get(self.url(annotation))
        response=self.save(annotation,expected=str(first.id))
        self.assertEqual(response.status_code,409);self.assertEqual(self.count(),2)
        self.assertIn('Review history',response.get_data(as_text=True))

    def test_save_next_previous_and_next_keep_filtered_cohort_and_last_returns_list(self):
        items=sorted([x for x in self.matching('L1','ambiguous') if self.service.review_record(x.id)['article'].source=='citizen'],
                     key=lambda x:(x.created_at,x.id),reverse=True)
        query='?label=ambiguous&source=citizen&page=1'
        first,second=items
        self.unlock(first,query)
        response=self.save(first,query=query,action='save_next')
        self.assertEqual(response.status_code,303)
        self.assertIn(str(second.id),response.location)
        context=parse_qs(urlsplit(response.location).query)
        self.assertEqual(context['label'],['ambiguous']);self.assertEqual(context['source'],['citizen'])
        self.assertEqual(context['page'],['2'])
        page=self.client.get(response.location)
        self.assertIn(str(first.id),page.get_data(as_text=True))
        self.assertIn('Previous',page.get_data(as_text=True))
        response=self.save(second,query='?label=ambiguous&source=citizen&page=2',action='save_next')
        self.assertEqual(response.status_code,303)
        self.assertTrue(response.location.startswith('/annotations/l1?'))
        self.assertEqual(self.count(),2)

    def test_save_next_pending_filter_uses_remaining_cohort_page(self):
        items = sorted(self.matching('L1', 'ambiguous'), key=lambda x: x.created_at, reverse=True)
        first, second = items[:2]
        query = '?label=ambiguous&review_status=not_reviewed&page=1'
        self.unlock(first, query)
        response = self.save(first, query=query, action='save_next')
        self.assertEqual(response.status_code, 303)
        self.assertIn(str(second.id), response.location)
        self.assertEqual(parse_qs(urlsplit(response.location).query)['page'], ['1'])
        rows, total = self.service.results('L1', {'label': 'ambiguous', 'review_status': 'not_reviewed'}, 1, 1)
        self.assertEqual(total, 2)
        self.assertEqual(rows[0][0].id, second.id)
        rows, total = self.service.results('L1', {'review_status': 'reviewed'}, 1, 25)
        self.assertEqual(total, 1)
        self.assertEqual(rows[0][0].id, first.id)

    def test_remote_disabled_session_expiry_and_configuration_rotation(self):
        annotation=self.matching('L1','ambiguous')[0];self.unlock(annotation)
        remote={'REMOTE_ADDR':'192.0.2.10'}
        html=self.client.get(self.url(annotation),base_url='https://localhost',environ_overrides=remote).get_data(as_text=True)
        self.assertNotIn('private-text',html)
        response=self.client.post(self.url(annotation),data={'action':'save','csrf_token':self.csrf()},
                                  base_url='https://localhost',environ_overrides=remote)
        self.assertEqual(response.status_code,403)
        self.app.config['HUMAN_REVIEW_TOKEN']='new-token'*5
        self.assertNotIn('private-text',self.client.get(self.url(annotation)).get_data(as_text=True))
        self.assertEqual(self.count(),0)
        with self.client.session_transaction() as session:session['human_review_started']=0
        self.assertFalse('private-text' in self.client.get(self.url(annotation)).get_data(as_text=True))

    def test_feature_flag_missing_identity_guideline_short_secrets_and_forwarded_requests(self):
        annotation=self.matching('L1','ambiguous')[0]
        for setting,value in [('HUMAN_REVIEW_ENABLED',False),('HUMAN_REVIEWER_ID',''),
                              ('HUMAN_REVIEW_GUIDELINE_VERSION',''),('HUMAN_REVIEW_TOKEN','short'),('SECRET_KEY','short')]:
            old=self.app.config[setting];self.app.config[setting]=value
            response=self.client.get(self.url(annotation));self.assertEqual(response.status_code,200)
            self.assertNotIn('name="review_token"',response.get_data(as_text=True))
            self.assertEqual(self.client.post(self.url(annotation),data={}).status_code,403)
            self.app.config[setting]=old
        response=self.client.get(self.url(annotation),headers={'X-Forwarded-For':'192.0.2.10'})
        self.assertNotIn('name="review_token"',response.get_data(as_text=True))
        self.assertEqual(self.count(),0)

    def test_content_missing_or_corrupt_does_not_leak_or_mutate(self):
        annotation=self.matching('L1','kenya')[0];self.unlock(annotation)
        self.objects.read_json.side_effect=None
        self.objects.read_json.return_value={'source':'wrong','article_text':'sensitive secret'}
        html=self.client.get(self.url(annotation)).get_data(as_text=True)
        self.assertIn('cannot be verified',html);self.assertNotIn('sensitive secret',html)
        self.objects.read_json.return_value=None
        self.assertIn('extraction is missing',self.client.get(self.url(annotation)).get_data(as_text=True))
        self.assertEqual(self.count(),0)

    def test_new_machine_result_does_not_inherit_old_review(self):
        annotation=self.matching('L1','kenya')[0];self.unlock(annotation);self.save(annotation)
        with self.sessions.begin() as session:
            new=AutomatedAnnotation(id=uuid4(),article_id=annotation.article_id,article_version_id=annotation.article_version_id,
                annotation_run_id=annotation.annotation_run_id,prerequisite_annotation_id=annotation.prerequisite_annotation_id,
                layer='L1',label='ambiguous',method_name=annotation.method_name,method_version=annotation.method_version,
                confidence=.5,evidence={},reason_codes=[],created_at=self.now+timedelta(days=1))
            session.add(new)
        summary=self.service.overview()['human_review']
        self.assertEqual(summary['counts']['L1']['reviewed'],0)
        self.assertEqual(summary['counts']['L1']['not_reviewed'],5)
        self.assertEqual(len(self.service.reviews.history(annotation.id)),1)

    def test_missing_migration_preserves_monitor_and_blocks_saves(self):
        self.service.reviews.available.cache_clear()
        with self.engine.begin() as connection:connection.exec_driver_sql('DROP TABLE public.human_validations')
        self.assertIsNone(self.service.overview()['human_review'])
        self.assertEqual(self.client.get('/annotations').status_code,200)
        self.assertIn('Review storage unavailable', self.client.get('/annotations/l1').get_data(as_text=True))
        self.assertEqual(self.client.get('/annotations/l1?review_status=confirmed').status_code,503)
        annotation=self.matching('L1','kenya')[0];self.unlock(annotation)
        self.assertEqual(self.save(annotation).status_code,503)
