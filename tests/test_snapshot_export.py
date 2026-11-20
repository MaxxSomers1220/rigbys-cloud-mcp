"""Paid export checks using synthetic records and isolated PostgreSQL."""
from copy import deepcopy
from datetime import datetime, timedelta
from email.message import Message
import asyncio
import gzip
import hashlib
import json
import secrets

from fastapi.testclient import TestClient
import psycopg
import pytest

from mcp_fixtures import GENERATED_AT, fixture_records
from rigbys_feed import snapshot_export
from rigbys_feed.database import publish_feed, record_failure
from rigbys_mcp import auth
from rigbys_mcp.app import create_app
from test_database import database  # noqa: F401 -- isolated PostgreSQL fixture
from test_mcp_http import HEADERS, assert_plain_error, payload, rpc, token_header

PATH = "/snapshot-export"
FEED_TIME = datetime.fromisoformat(GENERATED_AT)
PAID_REQUIRED = "Paid pass required — access information: https://mcp.rigbyscloud.com/redeem"


@pytest.fixture
def export_client(database, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", database.info.dsn)
    monkeypatch.setattr(auth, "utcnow", lambda: FEED_TIME)
    tokens = {}
    for label, tier, expires_at in (
        ("paid", "paid", FEED_TIME + timedelta(days=80)),
        ("free", "free", None),
        ("expired", "paid", FEED_TIME - timedelta(seconds=1)),
    ):
        prefix = "rgby_free_" if tier == "free" else "rgby_live_"
        token = prefix + secrets.token_urlsafe(32)
        tokens[label] = token
        key_hash = hashlib.sha256(token.encode()).hexdigest()
        database.execute(
            """INSERT INTO api_keys(key_hash,key_prefix,tier,email,expires_at,created_at)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            (key_hash, token[:12], tier, "synthetic-export-test@example.test", expires_at,
             FEED_TIME - timedelta(days=10)),
        )
        if tier == "paid":
            database.execute(
                """INSERT INTO redemptions(license_key_hash,api_key_hash,redeemed_at,gumroad_sale_ref)
                   VALUES (%s,%s,%s,%s)""",
                (hashlib.sha256(secrets.token_bytes(32)).hexdigest(), key_hash,
                 FEED_TIME - timedelta(days=10), "synthetic-export-test-" + label),
            )
    with TestClient(create_app()) as client:
        yield client, tokens


def sized_fixture(count):
    templates = fixture_records()
    for index in range(1, count + 1):
        record = deepcopy(templates[(index - 1) % len(templates)])
        identifier = f"fixture-{index:04d}"
        source_id = f"fixture-{index}"
        record["opportunity_id"] = identifier
        record["opportunity_number"] = f"TEST-26-{index:04d}"
        record["dedupe_key"] = hashlib.sha256(identifier.encode()).hexdigest()
        record["title_normalized"] += f' (synthetic export “{index}” — café λ)'
        record["source_ids"][0]["id"] = source_id
        for refs in record["source_refs"].values():
            for ref in refs:
                ref["source_id"] = source_id
                ref["url"] = f"https://www.grants.gov/search-results-detail/{source_id}"
        for field in ("linked_awards", "linked_papers", "links"):
            for edge in record[field]:
                edge["opportunity_id"] = identifier
        yield record


def fetch_export(client, token):
    response = client.get(PATH, headers=token_header(token))
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/gzip"
    assert response.headers["Cache-Control"] == "private, no-store"
    assert response.headers["Content-Length"] == str(len(response.content))
    assert "Content-Encoding" not in response.headers
    assert response.headers["Vary"] == "Authorization"
    assert int(response.headers["Content-Length"]) == len(response.content)
    disposition = Message()
    disposition["Content-Disposition"] = response.headers["Content-Disposition"]
    assert disposition.get_content_disposition() == "attachment"
    assert disposition.get_filename() == "rigbys-cloud-feed.json.gz"
    assert response.content[:2] == b"\x1f\x8b"
    body = gzip.decompress(response.content)
    assert token.encode() not in body
    document = json.loads(body)
    assert set(document) == {"feed_generated_at", "record_count", "opportunities"}
    assert response.headers["X-Feed-Generated-At"] == document["feed_generated_at"]
    assert response.headers["X-Feed-Record-Count"] == str(document["record_count"])
    assert len(document["opportunities"]) == document["record_count"]
    return response.content, document


def slot_ids(database):
    return dict(database.execute("SELECT slot, run_id FROM snapshot_exports").fetchall())


def stored_gzip(database, run_id, *, minimum_chunks=1):
    size, chunk_count = database.execute(
        "SELECT size_bytes,chunk_count FROM snapshot_exports WHERE run_id=%s", (run_id,),
    ).fetchone()
    rows = database.execute(
        """SELECT chunk_index,data FROM snapshot_export_chunks
           WHERE run_id=%s ORDER BY chunk_index""",
        (run_id,),
    ).fetchall()
    assert chunk_count >= minimum_chunks
    assert [index for index, _ in rows] == list(range(chunk_count))
    assert all(0 < len(chunk) <= snapshot_export._CHUNK_BYTES for _, chunk in rows)
    data = b"".join(chunk for _, chunk in rows)
    assert len(data) == size
    return data


def test_export_has_786_exact_canonical_records_and_matches_ten_mcp_gets(
    database, export_client, monkeypatch,
):
    monkeypatch.setattr(snapshot_export, "_CHUNK_BYTES", 1024)
    client, tokens = export_client
    run = publish_feed(database, list(sized_fixture(786)), GENERATED_AT, {}, {})
    content, export = fetch_export(client, tokens["paid"])
    assert export["feed_generated_at"] == GENERATED_AT
    assert export["record_count"] == 786
    assert slot_ids(database) == {"current": run}
    assert content == stored_gzip(database, run, minimum_chunks=2)

    records = export["opportunities"]
    canonical = database.execute('SELECT record FROM opportunities ORDER BY opportunity_id COLLATE "C"')
    for exported, (persisted,) in zip(records, canonical, strict=True):
        assert exported == persisted
        assert exported["feed_generated_at"] == GENERATED_AT
    assert len({record["opportunity_id"] for record in records}) == 786

    headers = {**HEADERS, **token_header(tokens["paid"])}
    for index in (0, 6, 11, 83, 170, 271, 415, 548, 701, 785):
        record = records[index]
        response = client.post(
            "/mcp", headers=headers,
            json=rpc("opportunity_get", {"opportunity_id": record["opportunity_id"]}, index + 1),
        )
        assert response.status_code == 200
        assert payload(response) == record


def test_export_requires_paid_header_and_rejects_expired_or_query_key(database, export_client):
    client, tokens = export_client
    publish_feed(database, fixture_records(), GENERATED_AT, {}, {})
    response = client.get(PATH, headers=token_header(tokens["free"]))
    assert_plain_error(response, 403)
    assert response.json() == {"error": PAID_REQUIRED}
    expired = client.get(PATH, headers=token_header(tokens["expired"]))
    assert_plain_error(expired, 401)
    assert "expired" in expired.json()["error"].lower()
    for refused in (
        client.get(PATH),
        client.get(PATH, params={"api_key": tokens["paid"]}),
        client.get(PATH, headers={"Authorization": "Bearer invalid"}),
        client.get(PATH, headers=token_header("rgby_live_" + secrets.token_urlsafe(32))),
    ):
        assert_plain_error(refused, 401)
        assert refused.headers["WWW-Authenticate"] == "Bearer"
        assert "Content-Disposition" not in refused.headers
        assert tokens["paid"] not in refused.text
    digest = hashlib.sha256(tokens["paid"].encode()).hexdigest()
    database.execute("UPDATE api_keys SET revoked_at=%s WHERE key_hash=%s", (FEED_TIME, digest))
    revoked = client.get(PATH, headers=token_header(tokens["paid"]))
    assert_plain_error(revoked, 401)
    assert "revoked" in revoked.json()["error"]


def test_export_and_mcp_share_the_existing_paid_quota(database, export_client):
    client, tokens = export_client
    records = fixture_records()
    publish_feed(database, records, GENERATED_AT, {}, {})
    digest = hashlib.sha256(tokens["paid"].encode()).hexdigest()
    database.execute("INSERT INTO rate_limit_counters VALUES (%s,%s,998)", (digest, FEED_TIME.date()))

    fetch_export(client, tokens["paid"])
    headers = {**HEADERS, **token_header(tokens["paid"])}
    response = client.post("/mcp", headers=headers,
                           json=rpc("opportunity_get", {"opportunity_id": records[0]["opportunity_id"]}, 1))
    assert payload(response)["opportunity_id"] == records[0]["opportunity_id"]

    refused = client.get(PATH, headers=token_header(tokens["paid"]))
    assert_plain_error(refused, 429)
    assert int(refused.headers["Retry-After"]) > 0
    assert database.execute("SELECT calls FROM rate_limit_counters WHERE key_hash=%s", (digest,)).fetchone() == (1000,)


def test_paid_client_gets_service_unavailable_without_a_published_artifact(database, export_client):
    client, tokens = export_client
    assert slot_ids(database) == {}
    response = client.get(PATH, headers=token_header(tokens["paid"]))
    assert_plain_error(response, 503)
    assert "Content-Disposition" not in response.headers


def test_export_retains_two_generations_and_preserves_them_after_failure(database, export_client, monkeypatch):
    client, tokens = export_client
    records = fixture_records()
    times = [(FEED_TIME + timedelta(days=day)).isoformat() for day in range(4)]
    first = publish_feed(database, records, times[0], {}, {})
    first_bytes, _ = fetch_export(client, tokens["paid"])

    records[0]["title_normalized"] = "Synthetic second public snapshot"
    second_records = records[:-1]
    second = publish_feed(database, second_records, times[1], {}, {})
    second_bytes, second_doc = fetch_export(client, tokens["paid"])
    assert second_doc["feed_generated_at"] == times[1]
    assert second_doc["record_count"] == len(second_records)
    assert slot_ids(database) == {"current": second, "previous": first}
    assert stored_gzip(database, first) == first_bytes

    records[0]["title_normalized"] = "Synthetic third public snapshot"
    third = publish_feed(database, records, times[2], {}, {})
    third_bytes, third_doc = fetch_export(client, tokens["paid"])
    assert third_doc["feed_generated_at"] == times[2]
    assert third_doc["record_count"] == len(records)
    assert third_doc["opportunities"][0]["title_normalized"] == records[0]["title_normalized"]
    assert slot_ids(database) == {"current": third, "previous": second}
    assert stored_gzip(database, second) == second_bytes
    assert database.execute(
        "SELECT count(*) FROM snapshot_export_chunks WHERE run_id=%s", (first,),
    ).fetchone() == (0,)

    records[0]["title_normalized"] = "Failed synthetic snapshot"
    bad_records = deepcopy(records)
    bad_records[0]["links"][0]["link_type"] = "trial"
    with pytest.raises(psycopg.errors.CheckViolation):
        publish_feed(database, bad_records, times[3], {}, {})
    record_failure(database, {}, "SourceError")

    def broken_chunks(_parts):
        yield b"partial synthetic export"
        raise RuntimeError("forced export write failure")

    with monkeypatch.context() as patch:
        patch.setattr(snapshot_export, "_fixed_chunks", broken_chunks)
        with pytest.raises(RuntimeError, match="forced export write failure"):
            publish_feed(database, records, times[3], {}, {})

    with pytest.raises(RuntimeError, match="forced export rollback"):
        with database.transaction():
            uncommitted = publish_feed(database, records, times[3], {}, {})
            assert slot_ids(database) == {"current": uncommitted, "previous": third}
            raise RuntimeError("forced export rollback")

    assert slot_ids(database) == {"current": third, "previous": second}
    assert database.execute(
        "SELECT DISTINCT run_id FROM snapshot_export_chunks ORDER BY run_id",
    ).fetchall() == [(second,), (third,)]
    assert stored_gzip(database, second) == second_bytes
    assert fetch_export(client, tokens["paid"]) == (third_bytes, third_doc)
    assert database.execute("SELECT count(*) FROM free_feed_snapshots").fetchone() == (3,)


def test_in_progress_download_survives_two_committed_rotations(database, export_client, monkeypatch):
    monkeypatch.setattr(snapshot_export, "_CHUNK_BYTES", 128)
    client, tokens = export_client
    original = publish_feed(database, fixture_records(), GENERATED_AT, {}, {})
    original_bytes = stored_gzip(database, original, minimum_chunks=3)
    dsn = database.info.dsn

    def publish_two_generations():
        with psycopg.connect(dsn, autocommit=True) as writer:
            writer.execute("SET lock_timeout = '5s'")
            records = fixture_records()
            records[0]["title_normalized"] = "Synthetic second generation"
            second = publish_feed(writer, records, FEED_TIME + timedelta(days=1), {}, {})
            records[0]["title_normalized"] = "Synthetic current generation"
            third = publish_feed(writer, records, FEED_TIME + timedelta(days=2), {}, {})
            return second, third

    async def read_during_rotation():
        async with snapshot_export.open_current_export() as export:
            assert export is not None
            assert export.feed_generated_at == GENERATED_AT
            assert export.record_count == 9
            first_chunk = await anext(export.chunks)
            second, third = await asyncio.to_thread(publish_two_generations)
            remaining = [chunk async for chunk in export.chunks]
            assert export.size_bytes == len(original_bytes)
            assert first_chunk + b"".join(remaining) == original_bytes
            return second, third

    second, third = asyncio.run(read_during_rotation())
    assert slot_ids(database) == {"current": third, "previous": second}
    assert database.execute(
        "SELECT count(*) FROM snapshot_export_chunks WHERE run_id=%s", (original,),
    ).fetchone() == (0,)
    _, current = fetch_export(client, tokens["paid"])
    assert current["feed_generated_at"] == (FEED_TIME + timedelta(days=2)).isoformat()
    assert current["opportunities"][0]["title_normalized"] == "Synthetic current generation"


def test_export_refuses_stale_artifact_after_success_without_export(database, export_client):
    client, tokens = export_client
    original = publish_feed(database, fixture_records(), GENERATED_AT, {}, {})
    assert slot_ids(database) == {"current": original}

    # An older builder image may record a success during a rolling upgrade.
    database.execute(
        """INSERT INTO feed_runs(feed_generated_at,status,source_counts,source_status)
           VALUES (%s,'success','{}','{}')""",
        (FEED_TIME + timedelta(days=1),),
    )
    response = client.get(PATH, headers=token_header(tokens["paid"]))
    assert_plain_error(response, 503)
    assert "Content-Disposition" not in response.headers
    assert slot_ids(database) == {"current": original}
