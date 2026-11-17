from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pgserver
import psycopg
from psycopg.types.json import Jsonb
import pytest

from mcp_fixtures import fixture_records,seed_feed
from rigbys_feed import database as persistence
from rigbys_mcp.snapshots import search_free,capture_snapshot
from test_database import database


def capture_time(conn):
    return conn.execute('SELECT max(captured_at) FROM free_feed_snapshots').fetchone()[0]


def test_seven_day_boundary_both_clocks_and_no_summary_search(database):
    seed_feed(database)
    captured=capture_time(database)
    early=search_free(database,'rare disease',as_of=captured+timedelta(days=7)-timedelta(microseconds=1))
    assert early['status']=='delayed_feed_unavailable'
    assert early['opportunities']==[] and early['feed_generated_at'] is None
    eligible=search_free(database,'rare disease',limit=25,as_of=captured+timedelta(days=7))
    assert eligible['status']=='delayed_snapshot'
    assert len(eligible['opportunities'])==8
    encoded=json.dumps(eligible)
    assert 'summary_short' not in encoded
    assert 'growth_score' not in encoded and 'gap_score' not in encoded
    assert 'methodology_version' not in encoded and 'extracted_requirements' not in encoded
    assert search_free(database,'verify source requirements',as_of=captured+timedelta(days=7))['opportunities']==[]
    for row in eligible['opportunities']:
        assert datetime.fromisoformat(row['feed_generated_at'])<=captured


def test_actual_capture_cannot_be_backdated_to_make_current_data_free(database):
    seed_feed(database,'2001-01-01T00:00:00+00:00')
    captured=capture_time(database)
    assert search_free(database,'rare disease',as_of=captured+timedelta(days=6,hours=23,minutes=59))['opportunities']==[]
    assert len(search_free(database,'rare disease',as_of=captured+timedelta(days=7),limit=25)['opportunities'])==8
    # Even a direct inserted timestamp is forced to actual statement time.
    run=database.execute("INSERT INTO feed_runs(feed_generated_at,status,source_counts,source_status) VALUES ('2001-01-02','success','{}','{}') RETURNING run_id").fetchone()[0]
    inserted=database.execute("INSERT INTO free_feed_snapshots(feed_run_id,feed_generated_at,captured_at,record_count) VALUES (%s,'2001-01-02','1990-01-01',1) RETURNING captured_at",(run,)).fetchone()[0]
    assert inserted>=captured


def test_generation_clock_must_also_be_aged(database):
    now=datetime.now(timezone.utc)
    seed_feed(database,(now+timedelta(days=2)).isoformat())
    captured=capture_time(database)
    assert search_free(database,'rare disease',as_of=captured+timedelta(days=7))['status']=='delayed_feed_unavailable'
    assert search_free(database,'rare disease',as_of=now+timedelta(days=9,microseconds=1))['status']=='delayed_snapshot'


def test_snapshot_is_immutable_and_mutable_current_feed_cannot_leak(database):
    records=seed_feed(database)
    captured=capture_time(database)
    stored=search_free(database,'cellular mechanisms',as_of=captured+timedelta(days=7))['opportunities'][0]
    changed=deepcopy(records)
    changed[0]['title_normalized']='Brand new secret title'
    changed[0]['summary_short']='Fresh private summary should never match free titles'
    persistence.publish_feed(database,changed,(captured+timedelta(days=1)).isoformat(),{}, {})
    # New generation is too recent at the old snapshot's first eligibility time.
    free=search_free(database,'cellular mechanisms',as_of=captured+timedelta(days=7))
    assert free['opportunities'][0]==stored
    assert search_free(database,'Brand new secret',as_of=captured+timedelta(days=7))['opportunities']==[]
    with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState,match='sealed'):
        database.execute('''INSERT INTO free_search_records
            (snapshot_id,opportunity_id,title_normalized,sponsor_normalized,deadline_parsed,
             award_amount_parsed,source_refs,fetched_at,deadline_precision)
            SELECT snapshot_id,'fresh-under-old-timestamp',title_normalized,sponsor_normalized,
                   deadline_parsed,award_amount_parsed,source_refs,fetched_at,deadline_precision
            FROM free_search_records ORDER BY snapshot_id LIMIT 1''')
    for sql in ("UPDATE free_search_records SET title_normalized='changed'",'DELETE FROM free_search_records',
                "UPDATE free_feed_snapshots SET captured_at='1990-01-01'",'DELETE FROM free_feed_snapshots',
                'TRUNCATE free_search_records'):
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
            database.execute(sql)


def test_whitelist_drops_poison_nested_refs_and_nonbasic_award_fields(database):
    records=fixture_records()
    refs=records[0]['source_refs']
    refs['summary_short']=[{'summary_short':'PRIVATE_SUMMARY','gap_score':99}]
    refs['gap_score']=[{'url':'https://private.example/SECRET_SCORE'}]
    refs['title_normalized'][0].update({'summary_short':'PRIVATE_SUMMARY',
                                       'nested':{'gap_score':99},'field':{'summary_short':'PRIVATE_SUMMARY'}})
    refs['title_normalized'].append({'source':'grants_gov','source_id':'fixture-1',
                                    'url':{'summary_short':'PRIVATE_SUMMARY'},'fetched_at':'wrong'})
    records[0]['award_amount_parsed'].update({'summary_short':'PRIVATE_SUMMARY','gap_score':99,
                                             'note':{'private':'PRIVATE_SUMMARY'}})
    persistence.publish_feed(database,records,'2001-01-01T00:00:00Z',{}, {})
    result=search_free(database,'cellular mechanisms',as_of=capture_time(database)+timedelta(days=7))
    encoded=json.dumps(result)
    assert 'PRIVATE_SUMMARY' not in encoded and 'SECRET_SCORE' not in encoded
    row=result['opportunities'][0]
    assert set(row['award_amount_parsed'])=={'currency','floor','ceiling'}
    assert set(row['source_refs'])<= {'title_normalized','sponsor_normalized','deadline_parsed',
                                    'award_amount_parsed','deadline_precision','fetched_at'}
    for group in row['source_refs'].values():
        for ref in group:
            assert set(ref)=={'source','source_id','url','fetched_at'}
            assert all(isinstance(value,str) for value in ref.values())


def test_snapshot_capture_rolls_back_with_full_publication_transaction(database):
    original=seed_feed(database)
    assert database.execute('SELECT count(*) FROM free_feed_snapshots').fetchone()[0]==1
    changed=deepcopy(original);changed[0]['title_normalized']='Must roll back'
    with pytest.raises(RuntimeError,match='forced'):
        with database.transaction():
            persistence.publish_feed(database,changed,'2026-11-18T05:00:00Z',{}, {})
            assert database.execute('SELECT count(*) FROM free_feed_snapshots').fetchone()[0]==2
            raise RuntimeError('forced rollback after capture')
    assert database.execute('SELECT count(*) FROM free_feed_snapshots').fetchone()[0]==1
    assert database.execute('SELECT count(*) FROM free_search_records').fetchone()[0]==9
    assert database.execute("SELECT title_normalized FROM opportunities WHERE opportunity_id='fixture-0001'").fetchone()[0]==original[0]['title_normalized']


def test_free_filters_caps_and_newest_eligible_generation(database):
    seed_feed(database,'2001-01-01T00:00:00Z')
    older=capture_time(database)
    changed=fixture_records();changed[0]['title_normalized']='Rare disease newer title'
    persistence.publish_feed(database,changed,'2001-01-02T00:00:00Z',{}, {})
    captured=capture_time(database)
    selected=search_free(database,'rare disease',sponsor='National Institutes of Health',
                         deadline_before='2026-12-31',deadline_after='2026-12-01',
                         limit=100,as_of=captured+timedelta(days=7))
    assert selected['feed_generated_at'].startswith('2001-01-02')
    assert {row['opportunity_id'] for row in selected['opportunities']}=={'fixture-0001','fixture-0002','fixture-0005'}
    assert next(row for row in selected['opportunities'] if row['opportunity_id']=='fixture-0001')['title_normalized']=='Rare disease newer title'
    run=database.execute('SELECT max(run_id) FROM feed_runs').fetchone()[0]
    assert capture_snapshot(database,run)==database.execute('SELECT snapshot_id FROM free_feed_snapshots WHERE feed_run_id=%s',(run,)).fetchone()[0]
    assert database.execute('SELECT count(*) FROM free_feed_snapshots').fetchone()[0]==2


def test_bootstrap_existing_feed_has_actual_age_zero(tmp_path,monkeypatch):
    old_migrations=tmp_path/'phase1';old_migrations.mkdir()
    old_migrations.joinpath('001_feed.sql').write_text(persistence.MIGRATIONS.joinpath('001_feed.sql').read_text())
    server=pgserver.get_server(tmp_path/'bootstrap_pg',cleanup_mode='delete')
    with psycopg.connect(server.get_uri(),autocommit=True) as conn:
        real=persistence.MIGRATIONS
        monkeypatch.setattr(persistence,'MIGRATIONS',old_migrations)
        persistence.migrate(conn)
        record=fixture_records()[0];record['feed_generated_at']='2001-01-01T00:00:00Z'
        fields={**record,'record':record}
        values=[Jsonb(fields.get(key)) if key in persistence._JSON_FIELDS and fields.get(key) is not None
                else fields.get(key) for key in persistence._COLUMNS]
        conn.execute('INSERT INTO opportunities ('+', '.join(persistence._COLUMNS)+') VALUES ('+
                     ', '.join(['%s']*len(values))+')',values)
        conn.execute("INSERT INTO feed_runs(feed_generated_at,status,source_counts,source_status) VALUES ('2001-01-01','success','{}','{}')")
        before=datetime.now(timezone.utc)
        monkeypatch.setattr(persistence,'MIGRATIONS',real)
        persistence.migrate(conn)
        captured=capture_time(conn)
        assert captured>=before
        assert search_free(conn,'rare disease',as_of=captured)['status']=='delayed_feed_unavailable'
        assert len(search_free(conn,'rare disease',as_of=captured+timedelta(days=7))['opportunities'])==1
