"""Local Phase 3 redemption checks with a synthetic Gumroad HTTP fixture."""
from html.parser import HTMLParser
import json
from fastapi.testclient import TestClient
import pytest
from rigbys_mcp.app import create_app
from test_database import database
from test_gumroad import provider,verifier_for


class Fields(HTMLParser):
    def __init__(self):super().__init__();self.token=None;self.key=None;self.in_key=False
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='input' and a.get('name')=='csrf_token':self.token=a['value']
        if a.get('id')=='api-key':self.in_key=True
    def handle_data(self,value):
        if self.in_key:self.key=value
    def handle_endtag(self,tag):
        if tag=='code':self.in_key=False


def parse(response):
    p=Fields();p.feed(response.text);return p


@pytest.fixture
def redeem_client(database,provider,monkeypatch):
    monkeypatch.setenv('DATABASE_URL',database.info.dsn)
    app=create_app();app.state.license_verifier=verifier_for(provider[1])
    with TestClient(app) as client:yield client


def submit(client,license_key,email):
    first=client.get('/redeem');token=parse(first).token
    return client.post('/redeem',data={'license_key':license_key,'email':email,'csrf_token':token})


def test_valid_once_invalid_and_replay(redeem_client,provider,database):
    license_key,purchase=provider;email=purchase['purchase']['email']
    result=submit(redeem_client,license_key,email)
    assert result.status_code==200
    raw=parse(result).key
    assert raw and raw.startswith('rgby_live_') and result.text.count(raw)==1
    assert license_key not in result.text
    assert 'codex mcp add rigbys-cloud' in result.text and 'claude mcp add --transport http rigbys-cloud' in result.text
    assert '90 days from redemption' in result.text and '1,000' in result.text and '20 searches/day' in result.text
    assert 'no-store' in result.headers['cache-control']
    assert parse(redeem_client.get('/redeem')).key is None
    second=submit(redeem_client,license_key,email)
    assert second.status_code==409 and 'already been redeemed' in second.text and raw not in second.text
    assert database.execute('SELECT count(*) FROM api_keys').fetchone()[0]==1
    assert database.execute('SELECT count(*) FROM redemptions').fetchone()[0]==1


def test_wrong_email_invalid_provider_and_no_config(redeem_client,provider,database,monkeypatch):
    license_key,purchase=provider;email=purchase['purchase']['email']
    wrong=submit(redeem_client,license_key,'wrong@example.invalid')
    assert wrong.status_code==400 and parse(wrong).key is None
    purchase['purchase']['refunded']=True
    bad=submit(redeem_client,license_key,email)
    assert bad.status_code==400 and license_key not in bad.text
    assert database.execute('SELECT count(*) FROM api_keys').fetchone()[0]==0
    from rigbys_mcp.gumroad import GumroadVerifier
    monkeypatch.delenv('GUMROAD_PRODUCT_ID',raising=False)
    redeem_client.app.state.license_verifier=GumroadVerifier()
    unavailable=submit(redeem_client,license_key,email)
    assert unavailable.status_code==503 and parse(unavailable).key is None
