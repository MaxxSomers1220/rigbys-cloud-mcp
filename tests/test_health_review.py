"""Independent real-HTTP health check against persisted synthetic build status."""
from contextlib import contextmanager

from rigbys_feed.database import publish_feed,record_failure
from mcp_fixtures import fixture_records,GENERATED_AT
from test_database import database  # noqa: F401 -- imported site fixture dependencies
from test_gumroad import provider  # noqa: F401
from test_redeem_review import site  # noqa: F401 -- actual uvicorn HTTP server


def test_http_health_preserves_success_timestamp_reports_failed_source_and_redacts_private_metadata(site,monkeypatch):
    from rigbys_mcp import health
    empty=site.client.get('/health')
    assert empty.status_code==200
    assert empty.json()['feed_generated_at'] is None
    assert empty.json()['last_build_status']=='never_run'
    assert empty.json()['server_version']=='1.0.0'
    sources={name:{'status':'ok','last_success_at':GENERATED_AT,
                   'oldest_response_at':GENERATED_AT,'reused_weekly_cache':name!='grants_gov'}
             for name in ('grants_gov','nih_reporter','openalex')}
    publish_feed(site.db,fixture_records(),GENERATED_AT,{'grants_gov_posted':9},sources)
    success=site.client.get('/health')
    assert success.status_code==200
    document=success.json()
    assert document['feed_generated_at']==GENERATED_AT
    assert document['last_build_status']=='success'
    assert document['server_version']=='1.0.0'
    assert set(document['last_build_status_per_source'].values())=={'ok'}
    assert document['sources']['nih_reporter']['reused_weekly_cache'] is True
    assert success.headers['cache-control']=='no-store'
    failed={**sources,'grants_gov':{**sources['grants_gov'],'status':'refresh_failed',
             'error':'synthetic-sensitive-marker','email':'synthetic-private@example.invalid',
             'database_details':'synthetic-sensitive-marker'}}
    record_failure(site.db,{'grants_gov_posted':9},'synthetic-sensitive-marker',failed)
    response=site.client.get('/health')
    assert response.status_code==200
    later=response.json()
    assert later['feed_generated_at']==GENERATED_AT
    assert later['last_build_status']=='failed'
    assert later['last_build_status_per_source']['grants_gov']=='refresh_failed'
    assert later['sources']['grants_gov']['last_success_at']==GENERATED_AT
    assert 'synthetic-sensitive-marker' not in response.text
    assert 'synthetic-private@example.invalid' not in response.text
    assert 'database_details' not in response.text
    assert site.db.execute('SELECT count(*) FROM opportunities').fetchone()[0]==9
    assert site.db.execute('SELECT count(*) FROM rate_limit_counters').fetchone()[0]==0
    assert site.calls==0
    @contextmanager
    def unavailable():
        raise RuntimeError('synthetic-sensitive-connection-failure')
        yield
    monkeypatch.setattr(health,'read_connection',unavailable)
    unavailable_response=site.client.get('/health')
    assert unavailable_response.status_code==503
    assert unavailable_response.json()['feed_generated_at'] is None
    assert unavailable_response.json()['server_version']=='1.0.0'
    assert 'synthetic-sensitive-connection-failure' not in unavailable_response.text
    assert unavailable_response.headers['cache-control']=='no-store'
