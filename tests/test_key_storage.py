"""Hash-only persistence and redemption-clock audit using synthetic fixtures."""
from datetime import datetime,timedelta,timezone
import hashlib
import json
import logging
from rigbys_mcp.auth import authorize,AccessError
from test_database import database
from test_gumroad import provider,verifier_for
from test_redeem import redeem_client,submit,parse
import pytest


def test_raw_credentials_absent_from_all_tables_and_logs(redeem_client,provider,database,monkeypatch,caplog):
    license_key,payload=provider
    caplog.set_level(logging.DEBUG)
    before=datetime.now(timezone.utc)
    payload['purchase']['sale_timestamp']=(before-timedelta(days=180)).isoformat()
    result=submit(redeem_client,license_key,payload['purchase']['email'])
    after=datetime.now(timezone.utc)
    assert result.status_code==200
    raw=parse(result).key;monkeypatch.setenv('RIGBYS_NEW_TEST_API_KEY',raw)
    row=database.execute('''SELECT k.key_hash,k.key_prefix,k.expires_at,k.created_at,
        r.license_key_hash,r.redeemed_at,r.gumroad_sale_ref FROM api_keys k
        JOIN redemptions r ON r.api_key_hash=k.key_hash''').fetchone()
    assert row[0]==hashlib.sha256(raw.encode()).hexdigest()
    assert row[1]==raw[:12] and row[1]!=raw
    assert row[4]==hashlib.sha256(license_key.strip().upper().encode()).hexdigest()
    assert before<=row[5]<=after and row[3]==row[5]
    assert row[2]-row[5]==timedelta(days=90)
    assert row[6]=='gumroad:'+payload['purchase']['sale_id']
    for (table,) in database.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'"):
        # Table identifiers come only from PostgreSQL's catalog, never user input.
        from psycopg import sql
        contents=database.execute(sql.SQL('SELECT row_to_json(t) FROM {} t').format(sql.Identifier(table))).fetchall()
        encoded=json.dumps(contents,default=str)
        assert raw not in encoded and license_key not in encoded
    assert raw not in caplog.text and license_key not in caplog.text
    assert authorize(raw,now=row[2]-timedelta(microseconds=1)).tier=='paid'
    with pytest.raises(AccessError) as err:authorize(raw,now=row[2])
    assert err.value.status==401 and 'expired' in str(err.value).lower()
