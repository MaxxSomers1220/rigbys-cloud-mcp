"""Independent browser/HTTP redemption checks with synthetic provider transport.

No request reaches Gumroad. Runtime licenses and API keys are test credentials,
not buyer data or evidence of a sale.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import hashlib
import json
import logging
import os
import re
import secrets
import socket
import threading
import time
from urllib.parse import parse_qs, urlencode

import httpx
import pytest
import uvicorn

from test_database import database  # noqa: F401 -- isolated PostgreSQL fixture
from test_gumroad import provider, verifier_for  # noqa: F401 -- synthetic provider fixture

KEY_RE=re.compile(r'rgby_live_[A-Za-z0-9_-]{16,128}')


class HiddenFields(HTMLParser):
    def __init__(self):
        super().__init__();self.values={}
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='input' and attrs.get('type')=='hidden':
            self.values[attrs['name']]=attrs.get('value','')


class Site:
    # Avoid fixture representations printing runtime credentials on failure.
    pass


@pytest.fixture
def site(database,provider,monkeypatch):
    from rigbys_mcp import keys
    from rigbys_mcp.app import create_app
    license_key,purchase=provider
    monkeypatch.setenv('DATABASE_URL',database.info.dsn)
    clock=datetime(2026,11,17,12,tzinfo=timezone.utc)
    monkeypatch.setattr(keys,'utcnow',lambda:clock)
    state=Site();state.db=database;state.license_key=license_key
    state.payload=deepcopy(purchase);state.status=200;state.calls=0
    state.allowed={license_key.upper()};state.error=None
    def backend(request):
        state.calls+=1
        assert str(request.url)=='https://api.gumroad.com/v2/licenses/verify'
        values=parse_qs(request.content.decode())
        assert values['increment_uses_count']==['false']
        supplied=values['license_key'][0]
        if state.error is not None:
            raise httpx.ConnectError(state.error,request=request)
        if supplied.strip().upper() not in state.allowed:
            # Deliberately hostile provider detail must never reach errors/logs.
            return httpx.Response(404,json={'success':False,'message':supplied})
        return httpx.Response(state.status,json=deepcopy(state.payload))
    app=create_app();app.state.license_verifier=verifier_for(state.payload,handler=backend)
    state.app=app;state.clock=clock
    listener=socket.socket();listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    listener.bind(('127.0.0.1',0));listener.listen(128)
    state.base='http://127.0.0.1:'+str(listener.getsockname()[1])
    server=uvicorn.Server(uvicorn.Config(app,log_level='critical',access_log=False,lifespan='on'))
    thread=threading.Thread(target=server.run,kwargs={'sockets':[listener]},daemon=True)
    thread.start();deadline=time.monotonic()+15
    while not server.started and thread.is_alive() and time.monotonic()<deadline:
        time.sleep(0.01)
    assert server.started,'Local redemption app failed to start'
    try:
        with httpx.Client(base_url=state.base,timeout=20,follow_redirects=False) as client:
            state.client=client
            yield state
    finally:
        server.should_exit=True;thread.join(timeout=15);listener.close()
        assert not thread.is_alive(),'Local redemption app failed to stop'


def form(site,client=None):
    client=client or site.client
    response=client.get('/redeem')
    assert response.status_code==200
    parser=HiddenFields();parser.feed(response.text)
    assert parser.values.get('csrf_token')
    return {**parser.values,'license_key':site.license_key,
            'email':'synthetic-buyer@example.invalid'}


def submit(site,changes=None,**kwargs):
    fields=form(site)
    fields.update(changes or {})
    return site.client.post('/redeem',data=fields,headers={'Origin':site.base},**kwargs)


def displayed_key(response):
    matches=KEY_RE.findall(response.text)
    assert len(matches)==1,'Successful page must display exactly one raw API-key value'
    return matches[0]


def assert_no_issue(site,response,status):
    assert response.status_code==status
    assert KEY_RE.search(response.text) is None
    assert site.license_key not in response.text
    assert 'Traceback' not in response.text
    assert 'postgresql://' not in response.text
    assert site.db.execute('SELECT count(*) FROM api_keys').fetchone()[0]==0
    assert site.db.execute('SELECT count(*) FROM redemptions').fetchone()[0]==0


def test_redeem_get_headers_form_and_csrf_cookie(site):
    response=site.client.get('/redeem')
    assert response.status_code==200
    assert response.headers['cache-control'].startswith('no-store')
    assert response.headers['pragma']=='no-cache'
    assert response.headers['referrer-policy']=='same-origin'
    assert response.headers['x-content-type-options']=='nosniff'
    assert response.headers['x-frame-options']=='DENY'
    csp=response.headers['content-security-policy']
    assert "default-src 'none'" in csp and "form-action 'self'" in csp and "frame-ancestors 'none'" in csp
    cookie=response.headers['set-cookie'].lower()
    assert 'httponly' in cookie and 'samesite=strict' in cookie and 'path=/redeem' in cookie
    assert 'type="password"' in response.text and 'autocomplete="off"' in response.text
    assert '90 days from redemption' in response.text and '1,000 tool calls/day' in response.text
    assert site.calls==0 and KEY_RE.search(response.text) is None


def test_csrf_origin_and_duplicate_fields_rejected_before_provider(site):
    fields=form(site);fields['csrf_token']='wrong-token'
    assert_no_issue(site,site.client.post('/redeem',data=fields,headers={'Origin':site.base}),403)
    fields=form(site);site.client.cookies.clear()
    assert_no_issue(site,site.client.post('/redeem',data=fields,headers={'Origin':site.base}),403)
    fields=form(site)
    assert_no_issue(site,site.client.post('/redeem',data=fields,headers={'Origin':'https://synthetic-evil.example.invalid'}),403)
    fields=form(site)
    assert_no_issue(site,site.client.post('/redeem',data=fields,headers={'Origin':site.base,'Sec-Fetch-Site':'cross-site'}),403)
    fields=form(site)
    duplicate=urlencode(list(fields.items())+[('license_key',site.license_key)])
    assert_no_issue(site,site.client.post('/redeem',content=duplicate,headers={'Origin':site.base,'Content-Type':'application/x-www-form-urlencoded'}),400)
    assert site.calls==0


def test_valid_redemption_is_one_time_hash_only_and_never_logged(site,caplog,monkeypatch):
    caplog.set_level(logging.INFO)
    response=submit(site)
    assert response.status_code==200
    raw=displayed_key(response)
    monkeypatch.setenv('RIGBYS_REVIEW_ISSUED_KEY',raw)
    digest=hashlib.sha256(raw.encode()).hexdigest()
    stored=site.db.execute('SELECT key_hash,key_prefix,tier,email,expires_at,created_at FROM api_keys').fetchone()
    assert stored[:4]==(digest,raw[:12],'paid','synthetic-buyer@example.invalid')
    assert stored[4]-stored[5]==timedelta(days=90)
    assert stored[5]==site.clock
    redemption=site.db.execute('SELECT license_key_hash,api_key_hash,redeemed_at,gumroad_sale_ref FROM redemptions').fetchone()
    assert redemption[:3]==(hashlib.sha256(site.license_key.encode()).hexdigest(),digest,site.clock)
    assert redemption[3].startswith('gumroad:')
    assert 'codex mcp add rigbys-cloud --url https://mcp.rigbyscloud.com/mcp --bearer-token-env-var RIGBYS_API_KEY' in response.text
    assert 'claude mcp add --transport http rigbys-cloud https://mcp.rigbyscloud.com/mcp' in response.text
    assert response.headers['cache-control'].startswith('no-store')
    assert response.headers['referrer-policy']=='no-referrer'
    assert raw not in str(response.headers) and site.license_key not in response.text
    again=site.client.get('/redeem')
    assert raw not in again.text
    replay=submit(site)
    assert replay.status_code==409 and KEY_RE.search(replay.text) is None
    assert 'already been redeemed' in replay.text
    assert site.db.execute('SELECT count(*) FROM api_keys').fetchone()[0]==1
    rows=site.db.execute('''SELECT row_to_json(k)::text FROM api_keys k
        UNION ALL SELECT row_to_json(r)::text FROM redemptions r''').fetchall()
    serialized=' '.join(row[0] for row in rows)
    assert raw not in serialized and site.license_key not in serialized
    assert raw not in caplog.text and site.license_key not in caplog.text


@pytest.mark.parametrize('kind',['wrong_license','wrong_email','refunded','disputed','provider_failure'])
def test_ineligible_and_unavailable_inputs_never_issue_keys_or_echo_secrets(site,kind,caplog):
    caplog.set_level(logging.INFO)
    changes={};status=400
    if kind=='wrong_license':changes['license_key']='synthetic-invalid-license-value'
    if kind=='wrong_email':changes['email']='synthetic-other-buyer@example.invalid'
    if kind in {'refunded','disputed'}:site.payload['purchase'][kind]=True
    if kind=='provider_failure':
        site.error=site.license_key+' provider error detail'
        status=503
    response=submit(site,changes)
    assert_no_issue(site,response,status)
    assert 'synthetic-other-buyer@example.invalid' not in response.text
    assert site.license_key not in caplog.text


def test_concurrent_case_alias_redemptions_create_exactly_one_key(site):
    fields=form(site);cookies=dict(site.client.cookies)
    def attempt(lower):
        body={**fields,'license_key':site.license_key.lower() if lower else site.license_key}
        with httpx.Client(base_url=site.base,cookies=cookies,timeout=20) as client:
            return client.post('/redeem',data=body,headers={'Origin':site.base})
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses=list(pool.map(attempt,[False,True]))
    assert sorted(r.status_code for r in responses)==[200,409]
    assert sum(len(KEY_RE.findall(r.text)) for r in responses)==1
    assert site.db.execute('SELECT count(*) FROM api_keys').fetchone()[0]==1
    assert site.db.execute('SELECT count(*) FROM redemptions').fetchone()[0]==1


def test_distinct_license_aliases_cannot_redeem_the_same_verified_sale_twice(site,monkeypatch):
    # Ordinary provider receipts may omit license_key; sale identity must still be unique.
    del site.payload['purchase']['license_key']
    alias='-'.join(secrets.token_hex(4).upper() for _ in range(4))
    monkeypatch.setenv('RIGBYS_REVIEW_LICENSE_ALIAS',alias)
    site.allowed.add(alias)
    assert submit(site).status_code==200
    response=submit(site,{'license_key':alias})
    assert response.status_code==409 and KEY_RE.search(response.text) is None
    assert site.db.execute('SELECT count(*) FROM api_keys').fetchone()[0]==1
    assert site.db.execute('SELECT count(*) FROM redemptions').fetchone()[0]==1


def test_malicious_form_values_wrong_content_type_and_oversized_chunked_form(site):
    response=submit(site,{'email':'bad\"><script>alert(1)</script> @example.invalid'})
    assert_no_issue(site,response,400)
    assert '<script>' not in response.text
    fields=form(site)
    assert_no_issue(site,site.client.post('/redeem',json=fields,headers={'Origin':site.base}),415)
    chunks=(b'x'*n for n in (4000,4000,1000))
    assert_no_issue(site,site.client.post('/redeem',content=chunks,
        headers={'Origin':site.base,'Content-Type':'application/x-www-form-urlencoded'}),413)
