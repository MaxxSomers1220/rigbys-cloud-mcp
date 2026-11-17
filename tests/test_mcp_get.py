import pytest
from rigbys_mcp.repository import Repository,QueryError
from test_database import database
from mcp_fixtures import seed_feed


def test_get_is_exact_persisted_record_including_evidence(database,monkeypatch):
    monkeypatch.setenv('DATABASE_URL',database.info.dsn);seed_feed(database)
    rows=database.execute('SELECT opportunity_id,record FROM opportunities ORDER BY opportunity_id').fetchall()
    for opportunity_id,record in rows:
        result=Repository().get(opportunity_id)
        assert result==record
        assert result['methodology_version']
        assert 'score_evidence' in result
        assert 'change_log' in result
        assert 'linked_trials' not in result
        assert all('join_confidence' in x for x in result['linked_awards']+result['linked_papers'])
    assert any(Repository().get(i)['score_evidence']['status']=='insufficient_data_neutral_placeholder' for i,_ in rows)
    with pytest.raises(QueryError,match='not found'):Repository().get("x' OR 1=1 --")


def test_get_id_validation():
    with pytest.raises(QueryError):Repository().get('')
