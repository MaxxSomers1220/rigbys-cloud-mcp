from copy import deepcopy
from datetime import date

import pgserver
import psycopg
import pytest

from rigbys_feed.cleaning import clean
from rigbys_feed.joining import join
from rigbys_feed.scoring import score
from rigbys_feed.summarizing import summarize
from rigbys_feed.database import migrate, publish_feed, record_failure, health, load_cache
from test_cleaning import item


@pytest.fixture
def database(tmp_path):
    server = pgserver.get_server(tmp_path/'pgdata',cleanup_mode='delete')
    with psycopg.connect(server.get_uri(),autocommit=True) as conn:
        migrate(conn)
        yield conn


def record():
    r=clean(item(),date(2026,11,17))
    r=join([r],[],[],[])[0]
    return summarize(score(r,date(2026,11,17)))


def publish(conn, records=None, timestamp='2026-11-17T05:00:00Z',caches=None):
    return publish_feed(conn,records or [record()],timestamp,
                        {'grants_gov':1,'nih_reporter_awards':0,'openalex':0},
                        {'grants_gov':{'status':'ok','last_success_at':timestamp}},caches)


def test_fresh_migration_idempotent_indexes_and_constraints(database):
    conn=database
    migrate(conn)
    tables={row[0] for row in conn.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")}
    assert {'opportunities','opportunity_links','api_keys','redemptions','rate_limit_counters',
            'feed_runs','source_cache','schema_migrations','free_feed_snapshots','free_search_records',
            'snapshot_exports','snapshot_export_chunks'} == tables
    assert conn.execute('SELECT count(*) FROM schema_migrations').fetchone()[0]==4
    indexes={row[0] for row in conn.execute("SELECT indexname FROM pg_indexes WHERE schemaname='public'")}
    assert {'opportunities_deadline_idx','opportunities_sponsor_idx','opportunities_gap_idx',
            'opportunities_search_idx','opportunity_links_target_idx'} <= indexes
    publish(conn)
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("INSERT INTO opportunity_links VALUES ('gg-123','trial','x','https://example.test',1,'wrong','{}')")
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("INSERT INTO opportunity_links VALUES ('gg-123','paper','x','https://example.test',1.1,'wrong','{}')")
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("INSERT INTO api_keys(key_hash,key_prefix,tier,email) VALUES ('raw-key','rgby_live_','paid','test@example.test')")


def test_full_record_round_trip_and_semantic_changes(database):
    conn=database
    original=record()
    publish(conn,[original])
    stored=conn.execute('SELECT record FROM opportunities').fetchone()[0]
    assert 'links' not in stored  # Internal write plan lives in opportunity_links.
    assert stored['linked_awards']==original['linked_awards']
    assert stored['linked_papers']==original['linked_papers']
    assert stored['score_evidence']==original['score_evidence']
    assert stored['research_coverage']==original['research_coverage']
    assert stored['source_refs']==original['source_refs']
    assert stored['feed_generated_at']=='2026-11-17T05:00:00Z'
    assert stored['change_log']==[]
    newer=deepcopy(original)
    newer['fetched_at']=newer['updated_at']='2026-11-18T05:00:00Z'
    for refs in newer['source_refs'].values():
        for ref in refs:
            if isinstance(ref,dict):
                ref['fetched_at']='2026-11-18T05:00:00Z'
    publish(conn,[newer],'2026-11-18T05:00:00Z')
    stored=conn.execute('SELECT record FROM opportunities').fetchone()[0]
    assert stored['change_log']==[]
    assert stored['updated_at']==original['updated_at']
    newer['title_normalized']='Updated source title'
    publish(conn,[newer],'2026-11-19T05:00:00Z')
    stored=conn.execute('SELECT record FROM opportunities').fetchone()[0]
    assert stored['change_log']==[{'at':'2026-11-19T05:00:00Z','fields':['title_normalized']}]
    assert stored['updated_at']=='2026-11-19T05:00:00Z'


def test_atomic_bad_feed_preserves_last_good_and_cache(database):
    conn=database
    timestamp='2026-11-17T05:00:00Z'
    cache={'research':{'payload':{'awards':[]},'fetched_at':timestamp}}
    publish(conn,caches=cache)
    changed=record();changed['title_normalized']='Must roll back'
    changed['links']=[{'link_type':'trial','target_id':'x','target_url':'https://example.test',
                       'join_confidence':1,'relationship':'invalid','evidence':{}}]
    with pytest.raises(psycopg.errors.CheckViolation):
        publish(conn,[changed],'2026-11-18T05:00:00Z',{'research':{'payload':{'awards':[1]},'fetched_at':'2026-11-18T05:00:00Z'}})
    record_failure(conn,{'grants_gov':1},'SourceError')
    state=health(conn)
    assert state['last_build_status']=='failed'
    assert state['feed_generated_at'].startswith('2026-11-17T05:00:00')
    assert conn.execute('SELECT title_normalized FROM opportunities').fetchone()[0]==record()['title_normalized']
    assert load_cache(conn,'research')['payload']=={'awards':[]}
    assert conn.execute('SELECT count(*) FROM feed_runs').fetchone()[0]==2
    assert load_cache(conn,'missing') is None


def test_removal_and_empty_feed_protection(database):
    conn=database
    one=record();two=deepcopy(one);two['opportunity_id']='gg-124';two['dedupe_key']='second'
    publish(conn,[one,two])
    publish(conn,[one],'2026-11-18T05:00:00Z')
    assert conn.execute('SELECT count(*) FROM opportunities').fetchone()[0]==1
    with pytest.raises(ValueError,match='empty'):
        publish_feed(conn,[],'2026-11-19T05:00:00Z',{}, {})
    assert conn.execute('SELECT count(*) FROM opportunities').fetchone()[0]==1


def test_failure_sanitizes_connection_urls(database):
    record_failure(database,{},'postgresql://redacted.invalid/database')
    error=database.execute('SELECT error FROM feed_runs').fetchone()[0]
    assert 'postgresql://' not in error


def test_applied_migration_checksum_cannot_be_rewritten(database,tmp_path,monkeypatch):
    from rigbys_feed import database as module
    altered=tmp_path/'altered_migrations';altered.mkdir()
    original=next(module.MIGRATIONS.glob('*.sql'))
    (altered/original.name).write_text(original.read_text()+'\n-- changed after application\n')
    monkeypatch.setattr(module,'MIGRATIONS',altered)
    with pytest.raises(RuntimeError,match='checksum changed'):
        module.migrate(database)
    assert database.execute('SELECT count(*) FROM schema_migrations').fetchone()[0]==4


def test_failed_fresh_migration_rolls_back_all_ddl(tmp_path,monkeypatch):
    from rigbys_feed import database as module
    broken=tmp_path/'broken';broken.mkdir()
    (broken/'001_broken.sql').write_text('CREATE TABLE rollback_probe (id integer); SELECT 1/0;')
    monkeypatch.setattr(module,'MIGRATIONS',broken)
    server=pgserver.get_server(tmp_path/'fresh_pgdata',cleanup_mode='delete')
    with psycopg.connect(server.get_uri(),autocommit=True) as conn:
        with pytest.raises(psycopg.errors.DivisionByZero):
            module.migrate(conn)
        assert conn.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public'").fetchone()[0]==0


def test_large_research_cache_chunked_roundtrip_cleanup_and_rollback(database,monkeypatch):
    from rigbys_feed import database as module
    import json
    monkeypatch.setattr(module,'_CACHE_CHUNK_BYTES',16*1024)
    value={'awards':[{'id':i,'description':'quote" slash\\ and Unicode λ🙂 '*100} for i in range(30)],
           'papers':[{'id':'W1','abstract':{'hello':[0,2]}}],'publications':[],'coverage':{'years':[2024,2025]}}
    timestamp='2026-11-17T05:00:00Z'
    cache={'research':{'payload':value,'fetched_at':timestamp}}
    publish(database,caches=cache)
    assert load_cache(database,'research')['payload']==value
    manifest=database.execute("SELECT payload FROM source_cache WHERE cache_name='research'").fetchone()[0]
    assert len(manifest['parts'])>1
    rows=database.execute('SELECT payload FROM source_cache WHERE cache_name=ANY(%s)',(manifest['parts'],)).fetchall()
    assert all(len(json.dumps(row[0]).encode())<=module._CACHE_CHUNK_BYTES for row in rows)
    # Force an error after chunk writes, verifying the full transaction rolls back.
    changed=deepcopy(value);changed['papers']=[{'id':'Must roll back'}]
    with pytest.raises(TypeError):
        publish_feed(database,[record()],timestamp,{}, {'invalid':object()},
                     {'research':{'payload':changed,'fetched_at':timestamp}})
    assert load_cache(database,'research')['payload']==value
    # Replacing a chunked snapshot with a small value removes all orphan parts.
    publish(database,caches={'research':{'payload':{'small':True},'fetched_at':timestamp}})
    assert load_cache(database,'research')['payload']=={'small':True}
    assert database.execute('SELECT count(*) FROM source_cache').fetchone()[0]==1


def test_chunked_cache_missing_or_corrupt_part_fails(database,monkeypatch):
    from rigbys_feed import database as module
    monkeypatch.setattr(module,'_CACHE_CHUNK_BYTES',1024)
    timestamp='2026-11-17T05:00:00Z'
    publish(database,caches={'research':{'payload':{'text':'abc'*2000},'fetched_at':timestamp}})
    manifest=database.execute("SELECT payload FROM source_cache WHERE cache_name='research'").fetchone()[0]
    database.execute('DELETE FROM source_cache WHERE cache_name=%s',(manifest['parts'][0],))
    with pytest.raises(RuntimeError,match='Incomplete'):
        load_cache(database,'research')
