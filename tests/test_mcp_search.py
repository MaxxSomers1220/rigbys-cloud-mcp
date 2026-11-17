from copy import deepcopy
from datetime import date
import pytest
from rigbys_feed.database import publish_feed
from rigbys_mcp.repository import Repository,QueryError
from test_database import database,record


def seed(conn,count=30):
    rows=[]
    for i in range(count):
        r=deepcopy(record());r['opportunity_id']=f'gg-{i:03d}';r['dedupe_key']=f'key-{i}'
        r['title_normalized']='Rare disease program' if i<28 else 'Solar energy program'
        r['summary_short']='Research opportunity for rare disease' if i<28 else 'Solar energy'
        r['deadline_parsed']=f'2027-01-{(i%27)+1:02d}T00:00:00+00:00'
        if i==27:r['deadline_parsed']=None;r['deadline_precision']='rolling'
        rows.append(r)
    publish_feed(conn,rows,'2026-11-17T00:00:00Z',{}, {})


def test_search_topic_dates_sponsor_caps_and_neutral_flags(database,monkeypatch):
    monkeypatch.setenv('DATABASE_URL',database.info.dsn);seed(database)
    repo=Repository()
    assert len(repo.search('rare disease')['opportunities'])==10
    capped=repo.search('rare disease',limit=100)['opportunities'];assert len(capped)==25
    r=repo.search('rare disease',sponsor='NIH',deadline_after=date(2027,1,5),deadline_before=date(2027,1,7))
    assert [x['opportunity_id'] for x in r['opportunities']]==['gg-004','gg-005','gg-006']
    assert r['opportunities'][0]['score_evidence']['status']=='insufficient_data_neutral_placeholder'
    assert r['opportunities'][0]['gap_score']==50
    assert repo.search('solar')['opportunities'][0]['opportunity_id'] in {'gg-028','gg-029'}
    assert repo.search('rare',sponsor="NIH' OR 1=1 --")['opportunities']==[]
    assert repo.search('rare',min_gap_score=51)['opportunities']==[]
    assert repo.search('rare',limit=25,min_gap_score=50)['opportunities']==[]
    assert repo.search('nonexistent')['opportunities']==[]


@pytest.mark.parametrize('kwargs',[{'topic':''},{'topic':'x','limit':0},{'topic':'x','min_gap_score':101},
                                  {'topic':'x','deadline_after':'2027-02-01','deadline_before':'2027-01-01'}])
def test_search_validation(kwargs):
    with pytest.raises(QueryError):Repository().search(**kwargs)


def test_min_gap_requires_observed_evidence_not_placeholder(database,monkeypatch):
    from psycopg.types.json import Jsonb
    monkeypatch.setenv('DATABASE_URL',database.info.dsn);seed(database,2)
    r=database.execute("SELECT record FROM opportunities WHERE opportunity_id='gg-000'").fetchone()[0]
    r['score_evidence']['status']='descriptive_proxy'
    database.execute("UPDATE opportunities SET record=%s WHERE opportunity_id='gg-000'",(Jsonb(r),))
    assert len(Repository().search('rare')['opportunities'])==2
    assert [x['opportunity_id'] for x in Repository().search('rare',min_gap_score=50)['opportunities']]==['gg-000']
