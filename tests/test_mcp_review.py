"""Independent contract regressions for persisted MCP reads (T2.2–T2.4)."""
from copy import deepcopy
import json

from psycopg import sql
import pytest

from rigbys_feed.database import publish_feed
from rigbys_mcp.repository import QueryError, Repository
from mcp_fixtures import GENERATED_AT, fixture_records, seed_feed
from test_database import database  # noqa: F401 -- isolated PostgreSQL fixture


def configure(database, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', database.info.dsn)
    return Repository()


def test_compact_search_omits_graph_refs_but_get_preserves_full_source_record(database, monkeypatch):
    repo = configure(database, monkeypatch)
    records = fixture_records()
    huge = [{'source':'openalex','source_id':f'W{i}',
             'evidence':'graph-only-provenance-marker'} for i in range(2000)]
    records[0]['source_refs']['linked_papers'] = huge
    records[0]['source_refs']['linked_awards'] = deepcopy(huge)
    records[0]['source_refs']['description'] = [{'source':'grants_gov','raw':'not-a-compact-field'}]
    publish_feed(database, records, GENERATED_AT, {}, {})
    compact = next(r for r in repo.search('cellular mechanisms')['opportunities']
                   if r['opportunity_id'] == records[0]['opportunity_id'])
    assert 'linked_papers' not in compact['source_refs']
    assert 'linked_awards' not in compact['source_refs']
    assert 'description' not in compact['source_refs']
    assert compact['source_refs']['title_normalized']
    assert compact['source_refs']['deadline_parsed']
    assert 'graph-only-provenance-marker' not in json.dumps(compact)
    assert len(json.dumps(compact)) < 20_000
    stored = database.execute('SELECT record FROM opportunities WHERE opportunity_id=%s',
                              (records[0]['opportunity_id'],)).fetchone()[0]
    assert repo.get(records[0]['opportunity_id']) == stored
    assert len(repo.get(records[0]['opportunity_id'])['source_refs']['linked_papers']) == 2000


def test_minimum_score_excludes_placeholders_even_at_zero_and_fifty(database, monkeypatch):
    repo = configure(database, monkeypatch)
    records = fixture_records()
    # A real score of50 is distinct from a neutral placeholder of50.
    records[0]['gap_score'] = 50
    assert records[0]['score_evidence']['status'] == 'descriptive_proxy'
    publish_feed(database, records, GENERATED_AT, {}, {})
    all_results = repo.search('rare disease', limit=25)['opportunities']
    assert len(all_results) == 8
    assert sum(r['score_evidence']['status'] == 'insufficient_data_neutral_placeholder'
               for r in all_results) == 2
    for minimum in (0,50):
        results = repo.search('rare disease', min_gap_score=minimum, limit=25)['opportunities']
        assert all(r['score_evidence']['status'] == 'descriptive_proxy' for r in results)
        assert all(r['gap_score'] >= minimum for r in results)
        assert any(r['opportunity_id'] == records[0]['opportunity_id'] for r in results)
    assert len(repo.search('rare disease', min_gap_score=0, limit=25)['opportunities']) == 6


def test_deadline_date_contract_independent_of_postgres_default_timezone(database, monkeypatch):
    repo = configure(database, monkeypatch)
    seed_feed(database)
    database.execute(sql.SQL("ALTER DATABASE {} SET timezone TO 'America/Los_Angeles'").format(
        sql.Identifier(database.info.dbname)))
    results = repo.search('rare disease', deadline_before='2026-12-01',
                          deadline_after='2026-12-01')['opportunities']
    assert [r['opportunity_id'] for r in results] == ['gg-fixture-0001']
    assert results[0]['deadline_parsed'].startswith('2026-12-01T00:00:00')
    assert results[0]['deadline_parsed'].endswith('+00:00')
    assert repo.search('rare disease', deadline_before='2026-11-30',
                       deadline_after='2026-11-30')['opportunities'][0]['opportunity_id'] == 'gg-fixture-0004'


def test_read_queries_do_not_mutate_feed_and_links_have_no_score_or_summary_fields(database, monkeypatch):
    repo = configure(database, monkeypatch)
    seed_feed(database)
    before = database.execute('SELECT opportunity_id,record FROM opportunities ORDER BY opportunity_id').fetchall()
    run_count = database.execute('SELECT count(*) FROM feed_runs').fetchone()[0]
    repo.search('rare disease', sponsor='NIH', limit=25)
    assert repo.search('rare disease', sponsor='NIH%')['opportunities'] == []
    assert repo.get(' gg-fixture-0001 ')['opportunity_id'] == 'gg-fixture-0001'
    response = repo.links('gg-fixture-0001')
    for edge in response['edges']:
        assert 'join_confidence' in edge and edge['target_url']
        assert not any('score' in key or 'summary' in key for key in edge)
        if edge['link_type'] == 'paper':
            assert edge['source_id'] == edge['via_award']
    assert database.execute('SELECT opportunity_id,record FROM opportunities ORDER BY opportunity_id').fetchall() == before
    assert database.execute('SELECT count(*) FROM feed_runs').fetchone()[0] == run_count
    for read in (repo.get,repo.links):
        with pytest.raises(QueryError,match='not found'):
            read("missing' OR 1=1 --")
        with pytest.raises(QueryError,match='opportunity_id'):
            read('x'*201)
