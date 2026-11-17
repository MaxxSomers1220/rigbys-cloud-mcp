"""Synthetic local purchase/key rotation checks; no real licenses or sale calls."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import hashlib
import secrets
import threading

import httpx
import psycopg
import pytest

from rigbys_mcp import auth,keys
from rigbys_mcp.gumroad import VerificationUnavailable
from test_database import database
from test_gumroad import provider,verifier_for

START=datetime(2026,11,17,8,0,tzinfo=timezone.utc)


def initial(database,monkeypatch,provider):
    license_key,payload=provider
    monkeypatch.setenv('DATABASE_URL',database.info.dsn)
    monkeypatch.setattr(keys,'utcnow',lambda:START)
    issued=keys.redeem(license_key,payload['purchase']['email'],verifier_for(payload))
    return license_key,payload,issued


def digest(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


def rejected_auth(raw,status=401,**kwargs):
    with pytest.raises(auth.AccessError) as error:
        auth.authorize(raw,**kwargs)
    assert error.value.status==status


def test_rotation_revokes_old_immediately_and_keeps_original_expiry(database,monkeypatch,provider):
    license_key,payload,old=initial(database,monkeypatch,provider)
    later=START+timedelta(days=30)
    monkeypatch.setattr(keys,'utcnow',lambda:later)
    replacement=keys.rotate(' '+license_key.lower()+' ',payload['purchase']['email'].upper(),verifier_for(payload))
    assert replacement.raw_key!=old.raw_key
    assert replacement.expires_at==old.expires_at==START+timedelta(days=90)
    rejected_auth(old.raw_key,now=later)
    assert auth.authorize(replacement.raw_key,now=later).tier=='paid'
    rejected_auth(replacement.raw_key,now=START+timedelta(days=90))
    oldrow=database.execute('SELECT revoked_at,rotated_at FROM api_keys WHERE key_hash=%s',(digest(old.raw_key),)).fetchone()
    assert oldrow==(later,later)
    row=database.execute('SELECT api_key_hash,redeemed_at FROM redemptions').fetchone()
    assert row==(digest(replacement.raw_key),START)
    assert database.execute('SELECT created_at FROM api_keys WHERE key_hash=%s',(row[0],)).fetchone()[0]==later


def test_rotation_copies_all_quota_days_and_cannot_reset_limit(database,monkeypatch,provider):
    license_key,payload,old=initial(database,monkeypatch,provider)
    day=START+timedelta(days=1)
    database.execute('''INSERT INTO rate_limit_counters(key_hash,day,calls) VALUES (%s,%s,1000),(%s,%s,73)''',
                     (digest(old.raw_key),day.date(),digest(old.raw_key),START.date()))
    monkeypatch.setattr(keys,'utcnow',lambda:day)
    new=keys.rotate(license_key,payload['purchase']['email'],verifier_for(payload))
    rejected_auth(new.raw_key,429,tool_name='opportunity_search',arguments={},charge=True,now=day)
    rows=database.execute('SELECT day,calls FROM rate_limit_counters WHERE key_hash=%s ORDER BY day',(digest(new.raw_key),)).fetchall()
    assert rows==[(START.date(),73),(day.date(),1000)]
    assert database.execute('SELECT count(*) FROM rate_limit_counters WHERE key_hash=%s',(digest(old.raw_key),)).fetchone()[0]==2
    # A subsequent, deliberate rotation still carries the same quota and clock.
    newest=keys.rotate(license_key,payload['purchase']['email'],verifier_for(payload))
    rejected_auth(new.raw_key,now=day)
    rejected_auth(newest.raw_key,429,tool_name='opportunity_search',charge=True,now=day)
    assert newest.expires_at==old.expires_at
    assert database.execute('SELECT redeemed_at FROM redemptions').fetchone()[0]==START


def test_rotation_never_extends_an_earlier_stored_expiry(database,monkeypatch,provider):
    license_key,payload,old=initial(database,monkeypatch,provider)
    earlier=START+timedelta(days=40)
    database.execute('UPDATE api_keys SET expires_at=%s WHERE key_hash=%s',(earlier,digest(old.raw_key)))
    monkeypatch.setattr(keys,'utcnow',lambda:START+timedelta(days=10))
    new=keys.rotate(license_key,payload['purchase']['email'],verifier_for(payload))
    assert new.expires_at==earlier


def test_failed_rotation_rolls_back_and_preserves_old_active(database,monkeypatch,provider):
    license_key,payload,old=initial(database,monkeypatch,provider)
    monkeypatch.setattr(keys,'generate_key',lambda:old.raw_key) # Forces a unique-hash failure.
    with pytest.raises(keys.KeyErrorResponse) as error:
        keys.rotate(license_key,payload['purchase']['email'],verifier_for(payload))
    assert error.value.status==503
    assert auth.authorize(old.raw_key,now=START).tier=='paid'
    assert database.execute('SELECT count(*) FROM api_keys').fetchone()[0]==1
    assert database.execute('SELECT api_key_hash FROM redemptions').fetchone()[0]==digest(old.raw_key)
    assert database.execute('SELECT revoked_at,rotated_at FROM api_keys').fetchone()==(None,None)


def test_wrong_email_license_sale_or_unredeemed_cannot_rotate(database,monkeypatch,provider):
    license_key,payload,old=initial(database,monkeypatch,provider)
    for license_value,email,verification in (
        (license_key,'wrong-buyer@example.invalid',verifier_for(payload)),
        (secrets.token_hex(32),payload['purchase']['email'],verifier_for(payload)),
        (license_key,payload['purchase']['email'],verifier_for({**payload,'success':False})),
    ):
        with pytest.raises(keys.KeyErrorResponse) as error:
            keys.rotate(license_value,email,verification)
        assert error.value.status==400
    another=deepcopy(payload);another['purchase']['sale_id']='synthetic-another-sale-not-a-real-sale'
    with pytest.raises(keys.KeyErrorResponse) as error:
        keys.rotate(license_key,payload['purchase']['email'],verifier_for(another))
    assert error.value.status==400
    assert auth.authorize(old.raw_key,now=START).tier=='paid'
    assert database.execute('SELECT count(*) FROM api_keys').fetchone()[0]==1


@pytest.mark.parametrize('state',['revoked','expired','missing_expiry','future_redemption','free'])
def test_inactive_or_free_pass_rejected(database,monkeypatch,provider,state):
    license_key,payload,old=initial(database,monkeypatch,provider)
    if state=='revoked':
        database.execute('UPDATE api_keys SET revoked_at=%s',(START,))
    elif state=='expired':
        database.execute('UPDATE api_keys SET expires_at=%s',(START,))
    elif state=='missing_expiry':
        database.execute('UPDATE api_keys SET expires_at=NULL')
    elif state=='future_redemption':
        database.execute('UPDATE redemptions SET redeemed_at=%s',(START+timedelta(days=1),))
    else:
        database.execute("UPDATE api_keys SET tier='free'")
    with pytest.raises(keys.KeyErrorResponse) as error:
        keys.rotate(license_key,payload['purchase']['email'],verifier_for(payload))
    assert error.value.status==(400 if state=='free' else 401)
    assert database.execute('SELECT count(*) FROM api_keys').fetchone()[0]==1


def test_provider_outage_does_not_change_key_state(database,monkeypatch,provider):
    license_key,payload,old=initial(database,monkeypatch,provider)
    with pytest.raises(keys.KeyErrorResponse) as error:
        keys.rotate(license_key,payload['purchase']['email'],verifier_for(payload,status=503))
    assert error.value.status==503
    assert auth.authorize(old.raw_key,now=START).tier=='paid'


def test_concurrent_same_generation_only_one_replacement_returned(database,monkeypatch,provider):
    license_key,payload,old=initial(database,monkeypatch,provider)
    barrier=threading.Barrier(2)
    def handle(request):
        barrier.wait(timeout=10)
        return httpx.Response(200,json=payload)
    verification=verifier_for(payload,handler=handle)
    def attempt():
        try:
            return keys.rotate(license_key,payload['purchase']['email'],verification)
        except keys.KeyErrorResponse as error:
            return error
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:attempt(),range(2)))
    issued=[r for r in results if isinstance(r,keys.IssuedKey)]
    errors=[r for r in results if isinstance(r,keys.KeyErrorResponse)]
    assert len(issued)==len(errors)==1
    assert errors[0].status==409
    assert database.execute('SELECT count(*) FROM api_keys').fetchone()[0]==2
    rejected_auth(old.raw_key,now=START)
    assert auth.authorize(issued[0].raw_key,now=START).tier=='paid'


def test_rotation_waits_for_old_shared_key_call_before_copying_quota(database,monkeypatch,provider):
    license_key,payload,old=initial(database,monkeypatch,provider)
    verified=threading.Event()
    def handle(request):
        verified.set()
        return httpx.Response(200,json=payload)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with psycopg.connect(database.info.dsn,autocommit=False) as inflight:
            inflight.execute('SELECT key_hash FROM api_keys WHERE key_hash=%s FOR SHARE',(digest(old.raw_key),))
            inflight.execute('INSERT INTO rate_limit_counters(key_hash,day,calls) VALUES (%s,%s,999)',
                             (digest(old.raw_key),START.date()))
            future=pool.submit(keys.rotate,license_key,payload['purchase']['email'],verifier_for(payload,handler=handle))
            assert verified.wait(timeout=10)
            assert not future.done()
            inflight.execute('UPDATE rate_limit_counters SET calls=1000 WHERE key_hash=%s',(digest(old.raw_key),))
            # Exiting this transaction commits the last in-flight call and
            # releases auth's shared key lock before rotation can copy usage.
        issued=future.result(timeout=10)
    rejected_auth(issued.raw_key,429,tool_name='opportunity_search',charge=True,now=START)


def test_rotation_caps_an_overlong_stored_expiry_at_original_redemption_clock(database,monkeypatch,provider):
    license_key,payload,old=initial(database,monkeypatch,provider)
    database.execute('UPDATE api_keys SET expires_at=%s WHERE key_hash=%s',
                     (START+timedelta(days=200),digest(old.raw_key)))
    monkeypatch.setattr(keys,'utcnow',lambda:START+timedelta(days=30))
    replacement=keys.rotate(license_key,payload['purchase']['email'],verifier_for(payload))
    assert replacement.expires_at==START+timedelta(days=90)


def test_failure_after_revocation_and_quota_copy_rolls_everything_back(database,monkeypatch,provider):
    license_key,payload,old=initial(database,monkeypatch,provider)
    database.execute('INSERT INTO rate_limit_counters(key_hash,day,calls) VALUES (%s,%s,500)',
                     (digest(old.raw_key),START.date()))
    database.execute('''CREATE FUNCTION synthetic_reject_rotation_update() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Synthetic forced update failure'; END; $$;
        CREATE TRIGGER synthetic_rotation_failure BEFORE UPDATE ON redemptions
        FOR EACH ROW EXECUTE FUNCTION synthetic_reject_rotation_update();''')
    with pytest.raises(keys.KeyErrorResponse) as error:
        keys.rotate(license_key,payload['purchase']['email'],verifier_for(payload))
    assert error.value.status==503
    assert database.execute('SELECT count(*) FROM api_keys').fetchone()[0]==1
    assert database.execute('SELECT revoked_at,rotated_at FROM api_keys').fetchone()==(None,None)
    assert database.execute('SELECT api_key_hash,redeemed_at FROM redemptions').fetchone()==(digest(old.raw_key),START)
    assert database.execute('SELECT key_hash,calls FROM rate_limit_counters').fetchall()==[(digest(old.raw_key),500)]
    assert auth.authorize(old.raw_key,now=START).tier=='paid'


def test_stored_email_must_match_reverified_purchase_owner(database,monkeypatch,provider):
    license_key,payload,old=initial(database,monkeypatch,provider)
    database.execute("UPDATE api_keys SET email='different-stored-owner@example.invalid'")
    with pytest.raises(keys.KeyErrorResponse) as error:
        keys.rotate(license_key,payload['purchase']['email'],verifier_for(payload))
    assert error.value.status==400
    assert database.execute('SELECT count(*) FROM api_keys').fetchone()[0]==1
    assert database.execute('SELECT revoked_at FROM api_keys').fetchone()[0] is None
