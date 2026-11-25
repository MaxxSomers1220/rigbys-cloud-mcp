import json
import pytest
from rigbys_mcp.repository import Repository,QueryError
from test_database import database
from mcp_fixtures import seed_feed


def test_links_equal_table_fields_and_graph_parents_without_insight(database,monkeypatch):
    monkeypatch.setenv('DATABASE_URL',database.info.dsn);seed_feed(database)
    repo=Repository();response=repo.links('gg-fixture-0001')
    rows=database.execute("SELECT opportunity_id,link_type,target_id,target_url,join_confidence,relationship,evidence->>'via_award' FROM opportunity_links WHERE opportunity_id='gg-fixture-0001' ORDER BY link_type,target_id").fetchall()
    fields=('opportunity_id','link_type','target_id','target_url','join_confidence','relationship','via_award')
    assert [{k:e[k] for k in fields} for e in response['edges']]==[dict(zip(fields,r)) for r in rows]
    for e in response['edges']:
        assert e['source_id']==('gg-fixture-0001' if e['link_type']=='award' else e['via_award'])
    assert 'score' not in json.dumps(response)
    assert 'summary' not in json.dumps(response)
    assert 'trial' not in json.dumps(response)
    assert repo.links('gg-fixture-0007')['edges']==[]
    with pytest.raises(QueryError,match='not found'):repo.links('unknown')
