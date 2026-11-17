"""Actual HTTP rotation checks; all receipts/keys are synthetic local fixtures."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import hashlib
import logging
import threading

import httpx
import pytest

from mcp_fixtures import seed_feed
from test_database import database  # noqa: F401 -- dependencies of imported site fixture
from test_gumroad import provider  # noqa: F401
from test_redeem_review import site, form, submit, displayed_key, KEY_RE  # noqa: F401
from test_mcp_http import HEADERS, rpc, payload


@pytest.fixture
def rotating(site,monkeypatch):
    from rigbys_mcp import auth,keys
    site.times=[site.clock]
    monkeypatch.setattr(keys,'utcnow',lambda:site.times[0])
    monkeypatch.setattr(auth,'utcnow',lambda:site.times[0])
    seed_feed(site.db)
    return site


def issue(site,monkeypatch):
    response=submit(site)
    assert response.status_code==200
    raw=displayed_key(response)
    monkeypatch.setenv('RIGBYS_REVIEW_ROTATION_ORIGINAL',raw)
    return raw


def rotate(site,changes=None):
    fields=form(site);fields.update(changes or {})
    return site.client.post('/redeem/rotate',data=fields,headers={'Origin':site.base})


def mcp(site,raw,name='opportunity_search',arguments=None):
    return site.client.post('/mcp',json=rpc(name,arguments),
                            headers={**HEADERS,'Authorization':'Bearer '+raw})


def digest(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


def uses(site,raw,day=None):
    row=site.db.execute('SELECT calls FROM rate_limit_counters WHERE key_hash=%s AND day=%s',
                         (digest(raw),day or site.times[0].date())).fetchone()
    return row[0] if row else 0


def test_rotation_revokes_old_key_new_mcp_works_and_preserves_clock_history_and_secrets(rotating,monkeypatch,caplog):
    site=rotating;caplog.set_level(logging.INFO)
    old=issue(site,monkeypatch)
    original=site.db.execute('SELECT redeemed_at FROM redemptions').fetchone()[0]
    expiry=site.db.execute('SELECT expires_at FROM api_keys WHERE key_hash=%s',(digest(old),)).fetchone()[0]
    for _ in range(3):assert mcp(site,old).status_code==200
    original_day=site.times[0].date()
    site.times[0]+=timedelta(days=7)
    for _ in range(2):assert mcp(site,old).status_code==200
    response=rotate(site)
    assert response.status_code==200
    new=displayed_key(response);monkeypatch.setenv('RIGBYS_REVIEW_ROTATED_KEY',new)
    assert new!=old and response.headers['cache-control'].startswith('no-store')
    row=site.db.execute('SELECT api_key_hash,redeemed_at FROM redemptions').fetchone()
    assert row==(digest(new),original)
    new_row=site.db.execute('SELECT expires_at,created_at,revoked_at FROM api_keys WHERE key_hash=%s',(digest(new),)).fetchone()
    assert new_row==(expiry,site.times[0],None)
    assert uses(site,new,original_day)==3 and uses(site,new)==2
    assert mcp(site,old).status_code==401
    listed=site.client.post('/mcp',json={'jsonrpc':'2.0','id':2,'method':'tools/list'},
                            headers={**HEADERS,'Authorization':'Bearer '+new})
    assert listed.status_code==200 and len(listed.json()['result']['tools'])==4
    assert uses(site,new)==2
    result=mcp(site,new)
    assert result.status_code==200 and len(payload(result)['opportunities'])==8
    assert uses(site,new)==3
    assert new not in site.client.get('/redeem').text
    stored=site.db.execute('''SELECT row_to_json(k)::text FROM api_keys k
        UNION ALL SELECT row_to_json(r)::text FROM redemptions r''').fetchall()
    text=' '.join(row[0] for row in stored)
    assert old not in text and new not in text and site.license_key not in text
    assert old not in caplog.text and new not in caplog.text and site.license_key not in caplog.text


def test_rotation_chain_cannot_reset_exhausted_daily_quota(rotating,monkeypatch):
    site=rotating;old=issue(site,monkeypatch)
    site.db.execute('INSERT INTO rate_limit_counters(key_hash,day,calls) VALUES (%s,%s,999)',
                    (digest(old),site.times[0].date()))
    response=rotate(site);assert response.status_code==200
    new=displayed_key(response);monkeypatch.setenv('RIGBYS_REVIEW_ROTATED_QUOTA_KEY',new)
    assert uses(site,new)==999
    assert mcp(site,new).status_code==200
    blocked=mcp(site,new)
    assert blocked.status_code==429 and int(blocked.headers['Retry-After'])>0
    assert uses(site,new)==1000
    response=rotate(site);assert response.status_code==200
    newest=displayed_key(response);monkeypatch.setenv('RIGBYS_REVIEW_ROTATED_QUOTA_KEY_LATEST',newest)
    assert uses(site,newest)==1000
    assert mcp(site,newest).status_code==429
    assert mcp(site,old).status_code==mcp(site,new).status_code==401
    assert site.db.execute('SELECT count(*) FROM api_keys WHERE revoked_at IS NULL').fetchone()[0]==1
    assert site.db.execute('SELECT count(*) FROM redemptions').fetchone()[0]==1


def test_rotation_provider_csrf_and_ownership_failure_leave_original_key_active(rotating,monkeypatch):
    site=rotating;old=issue(site,monkeypatch)
    fields=form(site);fields['csrf_token']='wrong-token';before=site.calls
    response=site.client.post('/redeem/rotate',data=fields,headers={'Origin':site.base})
    assert response.status_code==403 and site.calls==before
    response=rotate(site,{'email':'synthetic-other-buyer@example.invalid'})
    assert response.status_code==400 and KEY_RE.search(response.text) is None
    site.error=site.license_key+' synthetic transport detail'
    response=rotate(site)
    assert response.status_code==503 and site.license_key not in response.text
    site.error=None;site.payload['purchase']['refunded']=True
    assert rotate(site).status_code==400
    site.payload['purchase']['refunded']=False
    assert mcp(site,old).status_code==200
    assert site.db.execute('SELECT count(*) FROM api_keys').fetchone()[0]==1
    assert site.db.execute('SELECT api_key_hash FROM redemptions').fetchone()[0]==digest(old)


def test_concurrent_same_generation_rotations_issue_exactly_one_new_key(rotating,monkeypatch):
    site=rotating;old=issue(site,monkeypatch)
    barrier=threading.Barrier(2)
    original=site.app.state.license_verifier
    class BarrierVerifier:
        def verify(self,license_key,email):
            verified=original.verify(license_key,email)
            barrier.wait(timeout=10)
            return verified
    site.app.state.license_verifier=BarrierVerifier()
    fields=form(site);cookies=dict(site.client.cookies)
    def attempt(_):
        with httpx.Client(base_url=site.base,cookies=cookies,timeout=20) as client:
            return client.post('/redeem/rotate',data=fields,headers={'Origin':site.base})
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(attempt,range(2)))
    assert sorted(r.status_code for r in results)==[200,409]
    assert sum(len(KEY_RE.findall(r.text)) for r in results)==1
    new=displayed_key(next(r for r in results if r.status_code==200))
    monkeypatch.setenv('RIGBYS_REVIEW_ROTATION_RACE_WINNER',new)
    assert site.db.execute('SELECT count(*) FROM api_keys').fetchone()[0]==2
    assert site.db.execute('SELECT count(*) FROM api_keys WHERE revoked_at IS NULL').fetchone()[0]==1
    assert mcp(site,old).status_code==401 and mcp(site,new).status_code==200


def test_failed_mapping_update_rolls_back_new_key_revocation_and_counter_copy(rotating,monkeypatch):
    site=rotating;old=issue(site,monkeypatch)
    assert mcp(site,old).status_code==200
    site.db.execute('''CREATE FUNCTION synthetic_fail_rotation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Synthetic rotation mapping failure'; END; $$''')
    site.db.execute('''CREATE TRIGGER synthetic_rotation_failure BEFORE UPDATE ON redemptions
        FOR EACH ROW EXECUTE FUNCTION synthetic_fail_rotation()''')
    response=rotate(site)
    assert response.status_code==503 and KEY_RE.search(response.text) is None
    assert 'Synthetic rotation mapping failure' not in response.text
    assert site.db.execute('SELECT count(*) FROM api_keys').fetchone()[0]==1
    assert site.db.execute('SELECT revoked_at FROM api_keys').fetchone()[0] is None
    assert site.db.execute('SELECT api_key_hash FROM redemptions').fetchone()[0]==digest(old)
    assert uses(site,old)==1
    assert mcp(site,old).status_code==200


def test_expired_pass_cannot_get_ninety_more_days_via_rotation(rotating,monkeypatch):
    site=rotating;old=issue(site,monkeypatch)
    site.times[0]+=timedelta(days=90)
    response=rotate(site)
    assert response.status_code==401 and KEY_RE.search(response.text) is None
    assert 'expired' in response.text.lower()
    assert mcp(site,old).status_code==401
    assert site.db.execute('SELECT count(*) FROM api_keys').fetchone()[0]==1
    assert site.db.execute('SELECT count(*) FROM redemptions').fetchone()[0]==1
