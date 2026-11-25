"""Reviewed nonfederal consumer gates; synthetic data, isolated native PostgreSQL."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path

import pgserver
import psycopg
from psycopg.types.json import Jsonb
import pytest

from rigbys_feed import database as persistence
from rigbys_mcp.aggregation import aggregate
from rigbys_mcp import health
from test_database import database, record


STAMP='2026-11-24T14:47:08.992072+00:00'
PROGRAM='https://professional.heart.org/en/research-programs/aha-funding-opportunities/'
PDF='https://professional.heart.org/en/-/media/PHD-Files/Research/Funding-Opportunities-Media-Folder/'
REVIEWED_URLS=[PROGRAM+'career-development-award',PROGRAM+'innovative-project-award',
              PDF+'Career-Development-Award.pdf',PDF+'Career-Development-Award.pdf?sc_lang=en',
              PDF+'Innovative-Project-Award.pdf',PDF+'Innovative-Project-Award.pdf?sc_lang=en']
BASIC_FIELDS={'title_normalized','sponsor_normalized','deadline_parsed',
              'award_amount_parsed','deadline_precision','fetched_at'}


def reference(url=REVIEWED_URLS[0],**changes):
    return {'source':'aha','source_id':'2027-career-development-award','url':url,
            'fetched_at':STAMP,**changes}


def project(conn,refs):
    return conn.execute('SELECT rigbys_free_source_refs(%s)',(Jsonb(refs),)).fetchone()[0]


def test_005_allows_only_reviewed_basic_citations_and_preserves_federal_projection(database):
    for url in REVIEWED_URLS:
        ref=reference(url,raw_path='/private/raw.pdf',content_sha256='private-hash',
                      section_locator='private locator',eligibility=['private'],
                      summary_short='private summary',gap_score=99,
                      nested={'application_stages':['private']})
        refs={field:[ref] for field in BASIC_FIELDS}
        refs.update({field:[ref] for field in ['eligibility_parsed','submission_deadline_at',
                     'application_stages','summary_short','score_evidence','reviewed_terms']})
        projected=project(database,refs)
        assert set(projected)==BASIC_FIELDS
        for group in projected.values():
            assert group==[{k:ref[k] for k in ['source','source_id','url','fetched_at']}]
        assert 'private' not in json.dumps(projected)
    federal={'source':'grants_gov','source_id':'123-ab_C',
             'url':'https://www.grants.gov/search-results-detail/123-ab_C/',
             'fetched_at':STAMP,'score_evidence':{'private':True}}
    assert project(database,{'title_normalized':[federal]})=={
        'title_normalized':[{k:federal[k] for k in ['source','source_id','url','fetched_at']}]}


@pytest.mark.parametrize('url',[
    'http://professional.heart.org/en/research-programs/aha-funding-opportunities/career-development-award',
    'https://professional.heart.org.evil.invalid/en/research-programs/aha-funding-opportunities/career-development-award',
    'https://professional.heart.org@evil.invalid/en/research-programs/aha-funding-opportunities/career-development-award',
    'https://user:secret@professional.heart.org/en/research-programs/aha-funding-opportunities/career-development-award',
    'https://professional.heart.org:443/en/research-programs/aha-funding-opportunities/career-development-award',
    'https://www.professional.heart.org/en/research-programs/aha-funding-opportunities/career-development-award',
    'https://heart.org/en/research-programs/aha-funding-opportunities/career-development-award',
    PROGRAM,PROGRAM+'other-program',PROGRAM+'career-development-award/extra',
    PROGRAM+'career-development-award?sc_lang=en',
    PROGRAM+'career-development-award#private',
    PROGRAM+'career-development-award?summary_short=private',
    PDF+'Other-Award.pdf',PDF+'Career-Development-Award-2028.pdf',
    PDF+'Career-Development-Award.pdf?sc_lang=fr',
    PDF+'Career-Development-Award.pdf?sc_lang=en&gap_score=99',
    PDF+'Career-Development-Award.pdf?gap_score=99&sc_lang=en',
    PDF+'Career-Development-Award.pdf?sc_lang=en&sc_lang=en',
    PDF+'Career-Development-Award.pdf#score_evidence',
    PDF+'Career-Development-Award.pdf?sc_lang=en#summary_short',
    PDF+'../Funding-Opportunities-Media-Folder/Career-Development-Award.pdf',
    PDF+'%2e%2e/Career-Development-Award.pdf',
    PDF+'Career-Development-Award.pdf?sc_lang=en%26gap_score=99',
    PDF+'Career-Development-Award.pdf?sc_lang=en\nprivate',
    PDF+'Career-Development-Award.pdf?sc_lang=en\n',
    PDF+'Career-Development-Award.pdf ',
    PROGRAM+'career-development-award\t',
    'https://proposalcentral.com/',
])
def test_005_rejects_unreviewed_hosts_paths_credentials_queries_and_fragments(database,url):
    assert project(database,{'title_normalized':[reference(url)]})=={}


@pytest.mark.parametrize('change',[
    {'source':'nih_reporter'},{'source':'AHA'},{'source':{'aha':True}},
    {'source_id':7},{'source_id':{}},{'source_id':'x'*201},{'source_id':'unsafe/id'},
    {'url':{'url':REVIEWED_URLS[0]}},{'url':[REVIEWED_URLS[0]]},
    {'fetched_at':{}},{'fetched_at':None},{'fetched_at':7},
    {'fetched_at':'2026-11-24'},{'fetched_at':'2026-11-24T10:00:00'},
    {'fetched_at':'not a timestamp'},
])
def test_005_retains_scalar_and_timestamp_shape_gates(database,change):
    assert project(database,{'title_normalized':[reference(**change)]})=={}
    assert project(database,{'title_normalized':{'private':True}})=={}
    assert project(database,{'title_normalized':[None,7,[],reference(**change)]})=={}
    for top in [None,[],7,'private']:
        assert project(database,top)=={}


def test_005_upgrades_four_migrations_without_rewriting_sealed_snapshot_or_checksums(tmp_path,monkeypatch):
    original=persistence.MIGRATIONS;legacy=tmp_path/'legacy';legacy.mkdir()
    originals={p.name:p.read_bytes() for p in sorted(original.glob('00[1-4]_*.sql'))}
    assert len(originals)==4
    for name,body in originals.items():(legacy/name).write_bytes(body)
    server=pgserver.get_server(tmp_path/'upgrade-pgdata',cleanup_mode='delete')
    with psycopg.connect(server.get_uri(),autocommit=True) as conn:
        with monkeypatch.context() as patch:
            patch.setattr(persistence,'MIGRATIONS',legacy);persistence.migrate(conn)
        prior=dict(conn.execute('SELECT version,sha256 FROM schema_migrations').fetchall())
        federal=record();federal['source_refs']['title_normalized'].append(reference())
        persistence.publish_feed(conn,[federal],STAMP,{}, {})
        old=conn.execute('SELECT snapshot_id,source_refs FROM free_search_records').fetchall()
        assert '"source": "aha"' not in json.dumps(old[0][1])
        persistence.migrate(conn);persistence.migrate(conn)
        applied=dict(conn.execute('SELECT version,sha256 FROM schema_migrations').fetchall())
        assert len(applied)==5 and all(applied[name]==checksum for name,checksum in prior.items())
        assert conn.execute('SELECT snapshot_id,source_refs FROM free_search_records').fetchall()==old
        assert project(conn,{'title_normalized':[reference()]})['title_normalized']==[reference()]
        signature=conn.execute("SELECT pg_get_function_arguments(oid),prorettype::regtype::text,provolatile FROM pg_proc WHERE oid='rigbys_free_source_refs(jsonb)'::regprocedure").fetchone()
        assert signature==('refs jsonb','jsonb','i')
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
            conn.execute("UPDATE free_search_records SET title_normalized='must remain sealed'")
    assert all((original/name).read_bytes()==body for name,body in originals.items())
    assert all(prior[name]==hashlib.sha256(body).hexdigest() for name,body in originals.items())


def test_aggregation_namespaces_deduplicate_opportunities_without_research_or_citation_inflation():
    federal=record();federal['opportunity_id']='gg-123';federal['title_normalized']='Shared cardiovascular topic'
    federal['score_evidence']={'status':'descriptive_proxy'}
    for name in ['growth_score','momentum_score','novelty_score','gap_score']:federal[name]=60
    federal['linked_awards']=[{'target_id':'NIH-A1','fiscal_year':2026}]
    federal['linked_papers']=[{'target_id':'https://openalex.org/W1','publication_year':2026}]
    aha=deepcopy(federal);aha['opportunity_id']='aha-2027-career-development-award'
    aha['score_evidence']={'status':'insufficient_data_neutral_placeholder'}
    for name in ['growth_score','momentum_score','novelty_score','gap_score']:aha[name]=50
    aha['source_refs']['title_normalized']=[reference(),reference(REVIEWED_URLS[2])]
    # Source-ref metadata cannot reclassify a canonical ID or count two PDFs as two programs.
    federal['source_refs']['title_normalized']=[reference()]
    result=aggregate([federal,aha,deepcopy(aha)],'cardiovascular',as_of='2026-11-24')
    assert result['open_opportunity_count']==2
    assert result['source_counts']=={'grants_gov':1,'aha':1,'nih_reporter':1,'openalex':1}
    assert result['awarded_grant_count']==result['paper_count']==1
    assert result['scored_opportunity_count']==1 and result['neutral_placeholder_count']==1
    assert result['median_gap_score']==60
    assert result['top_neglected_subtopics'][0]['source_counts']==result['source_counts']
    only_federal=aggregate([federal],'cardiovascular',as_of='2026-11-24')
    assert only_federal['source_counts']=={'grants_gov':1,'nih_reporter':1,'openalex':1}
    only_aha=aggregate([aha],'cardiovascular',as_of='2026-11-24')
    assert only_aha['source_counts']=={'grants_gov':0,'aha':1,'nih_reporter':1,'openalex':1}
    assert only_aha['median_gap_score'] is None and only_aha['top_neglected_subtopics']==[]
    for identifier in ['NIH-A1','https://openalex.org/W1']:
        invalid=deepcopy(federal);invalid['opportunity_id']=identifier
        with pytest.raises(ValueError,match='namespace'):
            aggregate([invalid],'cardiovascular',as_of='2026-11-24')


def test_health_projects_only_safe_aha_status_fields_and_preserves_default_federal_shape(monkeypatch):
    @contextmanager
    def connection():yield object()
    state={'feed_generated_at':STAMP,'last_build_status':'success','last_attempt_at':STAMP,
           'last_failure':None,'sources':{name:{'status':'ok','last_success_at':STAMP}
                    for name in ['grants_gov','nih_reporter','openalex']}}
    monkeypatch.setattr(health,'read_connection',connection)
    monkeypatch.setattr(health,'feed_health',lambda _:state)
    before=health.status_document()
    assert set(before['sources'])=={'grants_gov','nih_reporter','openalex'}
    assert set(before['last_build_status_per_source'].values())=={'ok'}
    state['sources']['aha']={'status':'refresh_failed','oldest_response_at':STAMP,
        'last_success_at':'2026-11-24T14:47:08','reused_weekly_cache':False,
        'url':REVIEWED_URLS[0],'error':'private failure','raw_path':'/private/evidence',
        'verification':{'secret':'private'},'reviewed_terms':'private'}
    state['sources']['unreviewed']={'status':'ok','error':'private'}
    result=health.status_document()
    assert result['sources']['aha']=={'status':'refresh_failed','oldest_response_at':STAMP,
                                     'reused_weekly_cache':False}
    assert result['last_build_status_per_source']['aha']=='refresh_failed'
    encoded=json.dumps(result)
    assert 'professional.heart.org' not in encoded and 'private' not in encoded and 'unreviewed' not in encoded
    state['sources']['aha']={'status':{'secret':'private'},'last_success_at':7,'reused_weekly_cache':'false'}
    assert health.status_document()['sources']['aha']=={'status':'unknown'}
