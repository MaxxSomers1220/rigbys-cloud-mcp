"""Schema tests use runtime-generated hashes and synthetic references only.

No fixture here represents a purchase, a raw license, or an issued API key.
"""
import hashlib
import secrets

import pgserver
import psycopg
import pytest

from rigbys_feed import database as persistence
from test_database import database


def _hash():
    return hashlib.sha256(secrets.token_bytes(32)).hexdigest()


def _key(conn):
    digest=_hash()
    conn.execute('''INSERT INTO api_keys(key_hash,key_prefix,tier,email)
        VALUES (%s,'rgby_free_','free','schema-fixture@example.test')''',(digest,))
    return digest


def _redeem(conn,reference,key_hash=None):
    license_hash=_hash()
    conn.execute('''INSERT INTO redemptions(license_key_hash,api_key_hash,gumroad_sale_ref)
        VALUES (%s,%s,%s)''',(license_hash,key_hash or _key(conn),reference))
    return license_hash


def test_verified_sale_reference_is_unique_across_different_license_hashes(database):
    # This is a synthetic isolated test reference, not a verified live sale.
    reference='gumroad:'+secrets.token_hex(16)
    first=_redeem(database,reference)
    with pytest.raises(psycopg.errors.UniqueViolation) as error:
        _redeem(database,reference)
    assert error.value.diag.constraint_name=='redemptions_verified_sale_ref_unique_idx'
    assert database.execute('SELECT license_key_hash FROM redemptions').fetchall()==[(first,)]
    _redeem(database,'gumroad:'+secrets.token_hex(16))
    assert database.execute('SELECT count(*) FROM redemptions').fetchone()[0]==2


def test_unprefixed_legacy_references_can_remain_duplicated(database):
    legacy='synthetic-schema-test-not-a-sale:'+secrets.token_hex(16)
    first,second=_redeem(database,legacy),_redeem(database,legacy)
    rows=database.execute('''SELECT license_key_hash,gumroad_sale_ref FROM redemptions
        ORDER BY license_key_hash''').fetchall()
    assert rows==sorted([(first,legacy),(second,legacy)])
    definition=database.execute("SELECT indexdef FROM pg_indexes WHERE indexname='redemptions_verified_sale_ref_unique_idx'").fetchone()[0]
    assert 'UNIQUE INDEX' in definition
    assert "starts_with(gumroad_sale_ref, 'gumroad:'::text)" in definition


def test_upgrade_preserves_legacy_rows_and_migrations_are_immutable(tmp_path,monkeypatch):
    first_two=tmp_path/'first_two';first_two.mkdir()
    for filename in ('001_feed.sql','002_free_search_snapshots.sql'):
        first_two.joinpath(filename).write_text(persistence.MIGRATIONS.joinpath(filename).read_text())
    server=pgserver.get_server(tmp_path/'schema_upgrade',cleanup_mode='delete')
    with psycopg.connect(server.get_uri(),autocommit=True) as conn:
        real=persistence.MIGRATIONS
        monkeypatch.setattr(persistence,'MIGRATIONS',first_two)
        persistence.migrate(conn)
        legacy='synthetic-schema-test-not-a-sale:'+secrets.token_hex(16)
        _redeem(conn,legacy);_redeem(conn,legacy)
        before=conn.execute('SELECT * FROM redemptions ORDER BY license_key_hash').fetchall()
        monkeypatch.setattr(persistence,'MIGRATIONS',real)
        persistence.migrate(conn)
        persistence.migrate(conn)
        assert conn.execute('SELECT * FROM redemptions ORDER BY license_key_hash').fetchall()==before
        assert conn.execute('SELECT count(*) FROM schema_migrations').fetchone()[0]==5
        altered=tmp_path/'altered';altered.mkdir()
        for path in real.glob('*.sql'):
            altered.joinpath(path.name).write_text(path.read_text())
        with altered.joinpath('003_verified_gumroad_sales.sql').open('a') as changed:
            changed.write('\n-- attempt to rewrite an applied migration\n')
        monkeypatch.setattr(persistence,'MIGRATIONS',altered)
        with pytest.raises(RuntimeError,match='checksum changed'):
            persistence.migrate(conn)
        assert conn.execute('SELECT count(*) FROM schema_migrations').fetchone()[0]==5
        assert conn.execute('SELECT * FROM redemptions ORDER BY license_key_hash').fetchall()==before


def test_fresh_migrations_are_idempotent(database):
    persistence.migrate(database)
    assert database.execute('SELECT version FROM schema_migrations ORDER BY version').fetchall()==[
        ('001_feed.sql',),('002_free_search_snapshots.sql',),('003_verified_gumroad_sales.sql',),
        ('004_snapshot_exports.sql',),('005_nonfederal_source_refs.sql',)]
    assert database.execute('SELECT count(*) FROM redemptions').fetchone()[0]==0
