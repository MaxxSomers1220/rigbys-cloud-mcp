from contextlib import contextmanager
import json
from fastapi.testclient import TestClient
from rigbys_mcp.app import create_app
from rigbys_mcp import health
from rigbys_feed.database import publish_feed,record_failure
from test_database import database,record


def test_health_real_success_and_failed_attempt_preserves_feed(database,monkeypatch):
    monkeypatch.setenv('DATABASE_URL',database.info.dsn)
    generated='2026-11-17T04:54:38+00:00'
    sources={n:{'status':'ok','last_success_at':generated,'oldest_response_at':generated,'reused_weekly_cache':False}
             for n in ('grants_gov','nih_reporter','openalex')}
    publish_feed(database,[record()],generated,{},sources)
    with TestClient(create_app()) as client:
        response=client.get('/health');assert response.status_code==200
        result=response.json()
        assert result['feed_generated_at']==generated
        assert result['server_version']=='1.0.0'
        assert result['last_failure'] is None
        assert set(result['last_build_status_per_source'].values())=={'ok'}
        failed={**sources,'grants_gov':{'status':'refresh_failed','last_success_at':generated,
                                      'password':'must-not-leak','error':'must-not-leak'}}
        record_failure(database,{},'clinical_trials_gov: SourceError',failed)
        later=client.get('/health').json()
        assert later['feed_generated_at']==generated
        assert later['last_build_status']=='failed'
        assert later['last_failure']=={'attempted_at':later['last_attempt_at'],
                                      'failed_stage':'clinical_trials_gov','error_type':'SourceError'}
        assert later['sources']['grants_gov']['status']=='refresh_failed'
        assert 'must-not-leak' not in json.dumps(later)
        assert 'password' not in json.dumps(later)
        assert database.execute('SELECT count(*) FROM rate_limit_counters').fetchone()[0]==0

        publish_feed(database,[record()],'2026-11-18T04:54:38+00:00',{},sources)
        recovered=client.get('/health').json()
        assert recovered['last_build_status']=='success'
        assert recovered['last_failure']==later['last_failure']

        record_failure(database,{},'postgres_publication: ProgramLimitExceeded')
        limit=client.get('/health').json()
        assert limit['last_failure']=={'attempted_at':limit['last_attempt_at'],
            'failed_stage':'postgres_publication','error_type':'ProgramLimitExceeded'}

        record_failure(database,{},'transform: must_not_leak')
        unknown=client.get('/health').json()
        assert unknown['last_failure']=={'attempted_at':unknown['last_attempt_at'],
                                        'failed_stage':'transform','error_type':'unknown'}
        assert 'must_not_leak' not in json.dumps(unknown)

        record_failure(database,{},'must_not_leak: TypeError')
        assert client.get('/health').json()['last_failure'] is None


def test_health_empty_database_does_not_invent_feed(database,monkeypatch):
    monkeypatch.setenv('DATABASE_URL',database.info.dsn)
    with TestClient(create_app()) as client:
        r=client.get('/health').json()
        assert r['feed_generated_at'] is None and r['last_build_status']=='never_run'
        assert r['last_failure'] is None
        assert r['server_version']=='1.0.0'
        assert all(s['status']=='never_run' for s in r['sources'].values())


def test_health_unavailable_has_plain_error(database,monkeypatch):
    monkeypatch.setenv('DATABASE_URL',database.info.dsn)
    @contextmanager
    def fail():
        raise RuntimeError('sensitive-connection-details-must-not-appear')
        yield
    monkeypatch.setattr(health,'read_connection',fail)
    with TestClient(create_app()) as client:
        response=client.get('/health')
        assert response.status_code==503
        assert 'sensitive-connection' not in response.text
        assert response.json()['server_version']=='1.0.0'
        assert response.json()['feed_generated_at'] is None
        assert response.json()['last_failure'] is None
