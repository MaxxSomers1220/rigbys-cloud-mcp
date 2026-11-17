from datetime import datetime,timedelta,timezone
import hashlib
import json
import secrets
import os
import pytest
from rigbys_mcp.auth import authorize,AccessError
from test_database import database


def key(conn,monkeypatch,tier='paid',redeemed=None,expires=None,revoked=None,prefix=None,created=None):
    now=datetime.now(timezone.utc)
    raw='rgby_'+(prefix or ('live' if tier=='paid' else 'free'))+'_'+secrets.token_urlsafe(32)
    monkeypatch.setenv('RIGBYS_API_KEY',raw)
    digest=hashlib.sha256(raw.encode()).hexdigest()
    redeemed=redeemed or now-timedelta(days=1)
    if expires is None and tier=='paid':expires=redeemed+timedelta(days=90)
    conn.execute('''INSERT INTO api_keys(key_hash,key_prefix,tier,email,expires_at,revoked_at,created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s)''',(digest,raw[:12],tier,'synthetic@example.test',expires,revoked,created or now))
    if tier=='paid':
        conn.execute('INSERT INTO redemptions VALUES (%s,%s,%s,%s)',
                     (hashlib.sha256(secrets.token_bytes(32)).hexdigest(),digest,redeemed,'synthetic-local-test-not-a-sale'))
    return raw,digest


def test_valid_expired_redemption_clock_and_no_plaintext(database,monkeypatch,caplog):
    monkeypatch.setenv('DATABASE_URL',database.info.dsn)
    now=datetime.now(timezone.utc)
    raw,digest=key(database,monkeypatch,created=now-timedelta(days=180))
    assert authorize(raw,now=now).tier=='paid'  # Purchase/created date does not start the clock.
    database.execute('UPDATE api_keys SET expires_at=%s WHERE key_hash=%s',(now,digest))
    with pytest.raises(AccessError) as error:authorize(raw,now=now)
    assert error.value.status==401 and 'Key expired' in error.value.message
    assert 'mcp.rigbyscloud.com/redeem' in error.value.message
    rows=database.execute('SELECT row_to_json(k) FROM api_keys k').fetchall()
    assert raw not in json.dumps(rows) and raw not in caplog.text


def test_expiry_never_extends_beyond_original_redemption(database,monkeypatch):
    monkeypatch.setenv('DATABASE_URL',database.info.dsn);now=datetime.now(timezone.utc)
    raw,_=key(database,monkeypatch,redeemed=now-timedelta(days=91),expires=now+timedelta(days=90))
    with pytest.raises(AccessError) as error:authorize(raw,now=now)
    assert error.value.status==401 and 'expired' in error.value.message


def test_revocation_rotation_state_and_prefix_mismatch(database,monkeypatch):
    monkeypatch.setenv('DATABASE_URL',database.info.dsn);now=datetime.now(timezone.utc)
    raw,digest=key(database,monkeypatch)
    assert authorize(raw).key_hash==digest
    database.execute('UPDATE api_keys SET revoked_at=%s WHERE key_hash=%s',(now,digest))
    with pytest.raises(AccessError) as error:authorize(raw)
    assert error.value.status==401
    new,_=key(database,monkeypatch,redeemed=now-timedelta(days=10),expires=now+timedelta(days=80))
    assert authorize(new).tier=='paid'  # Seeded rotation state, no rotation endpoint.
    wrong,_=key(database,monkeypatch,prefix='free')
    with pytest.raises(AccessError) as error:authorize(wrong)
    assert error.value.status==401


@pytest.mark.parametrize('tier,cap',[('paid',1000),('free',20)])
def test_atomic_quota_boundary_and_retry_after(database,monkeypatch,tier,cap):
    monkeypatch.setenv('DATABASE_URL',database.info.dsn)
    now=datetime.now(timezone.utc).replace(hour=23,minute=59,second=59,microsecond=0)
    raw,digest=key(database,monkeypatch,tier=tier)
    database.execute('INSERT INTO rate_limit_counters VALUES (%s,%s,%s)',(digest,now.date(),cap-1))
    authorize(raw,'opportunity_search',{},True,now)
    with pytest.raises(AccessError) as error:authorize(raw,'opportunity_search',{},True,now)
    assert error.value.status==429 and error.value.retry_after==1
    assert database.execute('SELECT calls FROM rate_limit_counters').fetchone()[0]==cap
    # UTC day rollover gets a separate counter.
    authorize(raw,'opportunity_search',{},True,now+timedelta(seconds=1))
    assert database.execute('SELECT count(*) FROM rate_limit_counters').fetchone()[0]==2


def test_free_paid_tools_and_score_filter_refused_without_charge(database,monkeypatch):
    monkeypatch.setenv('DATABASE_URL',database.info.dsn)
    raw,_=key(database,monkeypatch,tier='free')
    for tool,args in [('opportunity_get',{}),('opportunity_links',{}),('gap_for_topic',{}),
                      ('opportunity_search',{'min_gap_score':0})]:
        with pytest.raises(AccessError) as error:authorize(raw,tool,args,True)
        assert error.value.status==403 and 'Paid pass required' in error.value.message
    authorize(raw)  # Initialization/listing does not consume quota.
    assert database.execute('SELECT count(*) FROM rate_limit_counters').fetchone()[0]==0


@pytest.mark.parametrize('raw',[None,'','Basic test','rgby_live_short','rgby_live_../../bad'])
def test_bad_keys_have_plain_error(raw):
    with pytest.raises(AccessError) as error:authorize(raw)
    assert error.value.status==401
