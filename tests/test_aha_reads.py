"""Real persisted AHA reads keep evidence and existing free/observed boundaries."""
from datetime import timedelta
import gzip
import json

from rigbys_feed import builder
from rigbys_feed.database import publish_feed
from rigbys_mcp.repository import Repository
from test_aha_pipeline import NOW, STAMP, batch
from test_database import database  # noqa: F401 -- disposable native PostgreSQL


def test_aha_detail_export_and_free_search_preserve_their_distinct_contracts(database, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', database.info.dsn)
    incoming = batch().records
    incoming[1]['application_stages'].append({
        'stage': 'full_application', 'required': True, 'invitation_required': True,
        'deadline_at': '2027-03-04T21:00:00+00:00', 'invitation_date': '2027-01-21',
    })
    records = builder.transform([], [], [], [], {}, NOW, additional_records=incoming)
    publish_feed(database, records, STAMP, {'aha': 2}, {'aha': {'status': 'fixture'}})
    repository = Repository()
    matching = repository.search('cardiovascular', sponsor='American Heart Association')
    assert len(matching['opportunities']) == 2
    for minimum in (0, 50, 51):
        assert repository.search('cardiovascular', min_gap_score=minimum)['opportunities'] == []
    result = repository.gap('cardiovascular')
    assert result['source_counts']['aha'] == 2 and result['source_counts']['grants_gov'] == 0
    assert result['neutral_placeholder_count'] == 2
    assert result['top_neglected_subtopics'] == result['top_crowded_subtopics'] == []
    identifier = 'aha-2027-innovative-project-award'
    detail = repository.get(identifier)
    assert detail['deadline_stage'] == 'pre_proposal'
    assert detail['application_stages'][1]['invitation_required'] is True
    assert detail['eligibility_geography']['scope'] == 'nationwide'
    assert detail['eligibility_parsed'] and detail['source_refs']['application_stages']
    assert detail['award_amount_basis'] == 'total' and detail['award_period_months'] == 24
    assert repository.links(identifier)['edges'] == []
    run_id = database.execute("SELECT run_id FROM snapshot_exports WHERE slot='current'").fetchone()[0]
    payload = json.loads(gzip.decompress(b''.join(bytes(row[0]) for row in database.execute(
        'SELECT data FROM snapshot_export_chunks WHERE run_id=%s ORDER BY chunk_index', (run_id,)))))
    assert payload['record_count'] == 2
    exported = next(record for record in payload['opportunities'] if record['opportunity_id'] == identifier)
    assert exported['application_stages'] == detail['application_stages']
    assert exported['eligibility_parsed'] == detail['eligibility_parsed']
    captured = database.execute('SELECT max(captured_at) FROM free_feed_snapshots').fetchone()[0]
    # Both the generation and capture really age; this does not backdate/seal
    # fabricated production history or bypass the existing seven-day gate.
    assert repository.search_free('award', as_of=captured)['opportunities'] == []
    assert repository.search_free('cardiovascular', as_of=captured + timedelta(days=8))['opportunities'] == []
    free = repository.search_free('award', as_of=captured + timedelta(days=8))['opportunities']
    assert len(free) == 2
    forbidden = {'summary_short', 'eligibility_parsed', 'eligibility_geography', 'application_stages',
                 'submission_deadline_at', 'award_period_months', 'score_evidence', 'gap_score'}
    for record in free:
        assert not forbidden.intersection(record)
        assert record['deadline_precision'] == 'date'
        for refs in record['source_refs'].values():
            for reference in refs:
                assert set(reference) == {'source', 'source_id', 'url', 'fetched_at'}
                assert reference['source'] == 'aha'
