"""Transactional feed persistence. Call with an autocommit psycopg connection.

DATABASE_URL belongs to the calling process environment; this module never
constructs, stores, logs, or prints database credentials.
"""
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path

from psycopg.types.json import Jsonb

_PACKAGE_MIGRATIONS = Path(__file__).resolve().parent / 'migrations'
MIGRATIONS = (_PACKAGE_MIGRATIONS if _PACKAGE_MIGRATIONS.is_dir()
              else Path(__file__).resolve().parents[2] / 'migrations')
_JSON_FIELDS = {'eligibility_parsed', 'award_amount_parsed', 'source_ids',
                'extracted_requirements', 'source_refs', 'change_log', 'record'}
_COLUMNS = ('opportunity_id', 'dedupe_key', 'title_normalized', 'sponsor_normalized',
            'deadline_parsed', 'eligibility_parsed', 'award_amount_parsed', 'source_ids',
            'growth_score', 'momentum_score', 'novelty_score', 'gap_score',
            'methodology_version', 'summary_short', 'extracted_requirements',
            'feed_generated_at', 'fetched_at', 'updated_at', 'source_refs', 'change_log', 'record')
_VOLATILE = {'feed_generated_at', 'fetched_at', 'updated_at', 'change_log', 'raw_path', 'sha256'}
# PostgreSQL JSONB has a per-element length ceiling. Keep research snapshots in
# bounded rows, rather than ever serializing a complete large array into JSONB.
_CACHE_CHUNK_BYTES = 8 * 1024 * 1024
_CACHE_MANIFEST_KEY = '__rigbys_cache_v1__'
_CACHE_PART_PREFIX = '__rigbys_cache_chunk_v1__:'



def migrate(conn):
    """Apply each immutable SQL file exactly once; failed DDL is rolled back."""
    paths = sorted(MIGRATIONS.glob('*.sql'))
    if not paths:
        raise RuntimeError('No packaged SQL migrations found')
    with conn.transaction():
        conn.execute('SELECT pg_advisory_xact_lock(724421700)')
        conn.execute('''CREATE TABLE IF NOT EXISTS schema_migrations (
            version text PRIMARY KEY, sha256 text NOT NULL,
            applied_at timestamptz NOT NULL DEFAULT now())''')
        applied = dict(conn.execute('SELECT version, sha256 FROM schema_migrations').fetchall())
        for path in paths:
            sql = path.read_text()
            checksum = hashlib.sha256(sql.encode()).hexdigest()
            if path.name in applied:
                if applied[path.name] != checksum:
                    raise RuntimeError('Applied migration checksum changed: '+path.name)
                continue
            conn.execute(sql)
            conn.execute('INSERT INTO schema_migrations(version, sha256) VALUES (%s,%s)',
                         (path.name, checksum))


def _semantic(value):
    if isinstance(value, dict):
        return {k:_semantic(v) for k,v in value.items() if k not in _VOLATILE}
    if isinstance(value, list):
        return [_semantic(v) for v in value]
    return value


def _iso(value):
    return value.isoformat() if isinstance(value, datetime) else value


def publish_feed(conn, records, generated_at, source_counts, source_status, caches=None):
    """Publish the entire candidate feed, edges, source cache and success atomically.

    An empty candidate is rejected so an upstream outage cannot erase a good feed.
    Absent records are removed only within the successfully committed transaction.
    """
    if not records:
        raise ValueError('Refusing to publish an empty feed')
    ids = [record['opportunity_id'] for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate opportunity IDs in candidate feed')
    generated_at = _iso(generated_at)
    with conn.transaction():
        conn.execute('SELECT pg_advisory_xact_lock(724421701)')
        previous = dict(conn.execute('SELECT opportunity_id, record FROM opportunities').fetchall())
        conn.execute('DELETE FROM opportunities WHERE NOT (opportunity_id = ANY(%s))', (ids,))
        sql = ('INSERT INTO opportunities ('+', '.join(_COLUMNS)+') VALUES ('+
               ', '.join(['%s']*len(_COLUMNS))+') ON CONFLICT(opportunity_id) DO UPDATE SET '+
               ', '.join(f'{c}=EXCLUDED.{c}' for c in _COLUMNS if c != 'opportunity_id'))
        for incoming in records:
            record = dict(incoming)
            edges = record.pop('links')
            prior = previous.get(record['opportunity_id'])
            changes = deepcopy(prior.get('change_log', [])) if prior else []
            if prior:
                old, new = _semantic(prior), _semantic(record)
                fields = sorted(key for key in set(old) | set(new) if old.get(key) != new.get(key))
                if fields:
                    changes.append({'at':generated_at, 'fields':fields})
                    record['updated_at'] = generated_at
                else:
                    record['updated_at'] = prior['updated_at']
            record['change_log'] = changes
            record['feed_generated_at'] = generated_at
            # Set all typed plan fields and retain the complete five-layer record.
            fields = {**record, 'record':record}
            values = [Jsonb(fields.get(key)) if key in _JSON_FIELDS and fields.get(key) is not None
                      else fields.get(key) for key in _COLUMNS]
            conn.execute(sql, values)
            conn.execute('DELETE FROM opportunity_links WHERE opportunity_id=%s', (record['opportunity_id'],))
            for edge in edges:
                conn.execute('''INSERT INTO opportunity_links
                    (opportunity_id,link_type,target_id,target_url,join_confidence,relationship,evidence)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)''',
                    (record['opportunity_id'],edge['link_type'],edge['target_id'],edge['target_url'],
                     edge['join_confidence'],edge['relationship'],Jsonb(edge['evidence'])))
        for name, cache in (caches or {}).items():
            _save_cache(conn, name, cache)
        run_id = conn.execute('''INSERT INTO feed_runs
            (feed_generated_at,status,source_counts,source_status) VALUES (%s,'success',%s,%s)
            RETURNING run_id''', (generated_at,Jsonb(source_counts),Jsonb(source_status))).fetchone()[0]
        from rigbys_mcp.snapshots import capture_snapshot
        from .snapshot_export import publish_current_export
        capture_snapshot(conn, run_id)
        publish_current_export(conn, run_id)
    return run_id


def record_failure(conn, source_counts, error, source_status=None):
    """Record a sanitized failure; the last successful feed remains untouched."""
    # Only a controlled error class/code should be supplied, never exception text
    # from a connection (which can contain a DSN or password).
    safe_error = str(error)
    if any(marker in safe_error.lower() for marker in ('postgres://','postgresql://','password=', '://')):
        safe_error = 'Feed build failed; sensitive details omitted'
    safe_error = safe_error[:500]
    with conn.transaction():
        previous = conn.execute("SELECT source_status FROM feed_runs WHERE status='success' ORDER BY run_id DESC LIMIT 1").fetchone()
        conn.execute('''INSERT INTO feed_runs(status,source_counts,source_status,error)
            VALUES ('failed',%s,%s,%s)''', (Jsonb(source_counts),Jsonb(source_status if source_status is not None else (previous[0] if previous else {})),safe_error))


def health(conn):
    latest = conn.execute('SELECT status, attempted_at, source_status FROM feed_runs ORDER BY run_id DESC LIMIT 1').fetchone()
    good = conn.execute("SELECT feed_generated_at,source_status,source_counts FROM feed_runs WHERE status='success' ORDER BY run_id DESC LIMIT 1").fetchone()
    return {'feed_generated_at':_iso(good[0]) if good else None,
            'last_build_status':latest[0] if latest else 'never_run',
            'last_attempt_at':_iso(latest[1]) if latest else None,
            'sources':latest[2] if latest else {}, 'source_counts':good[2] if good else {},
            'server_version':'feed-only-0.1.0'}


def _cache_namespace(name):
    return _CACHE_PART_PREFIX + hashlib.sha256(name.encode()).hexdigest() + ':'


def _save_cache(conn, name, cache):
    """Write a legacy small value or a manifest plus bounded JSON-text chunks.

    Called only inside publish_feed's transaction. Splitting the serialized JSON
    text also supports nested arrays and objects without schema assumptions.
    """
    if name.startswith(_CACHE_PART_PREFIX):
        raise ValueError('Reserved cache namespace')
    serialized = json.dumps(cache['payload'], ensure_ascii=True, separators=(',', ':'))
    namespace = _cache_namespace(name)
    conn.execute('DELETE FROM source_cache WHERE starts_with(cache_name, %s)', (namespace,))
    if len(serialized) <= _CACHE_CHUNK_BYTES:
        value = cache['payload']
    else:
        # Each ASCII text character can require at most two bytes when encoded
        # within the chunk's JSON string. Leave envelope overhead below the cap.
        size = max(1, (_CACHE_CHUNK_BYTES - 100)//2)
        parts, digest = [], hashlib.sha256()
        for index, offset in enumerate(range(0, len(serialized), size)):
            part_name = namespace + f'{index:08d}'
            chunk = serialized[offset:offset+size]
            digest.update(chunk.encode('ascii'))
            conn.execute('INSERT INTO source_cache(cache_name,payload,fetched_at) VALUES (%s,%s,%s)',
                         (part_name,Jsonb({'data':chunk}),cache['fetched_at']))
            parts.append(part_name)
        value = {_CACHE_MANIFEST_KEY:'json-text-chunks', 'parts':parts,
                 'sha256':digest.hexdigest(), 'serialized_bytes':len(serialized)}
    conn.execute('''INSERT INTO source_cache(cache_name,payload,fetched_at) VALUES (%s,%s,%s)
        ON CONFLICT(cache_name) DO UPDATE SET payload=EXCLUDED.payload,fetched_at=EXCLUDED.fetched_at''',
        (name,Jsonb(value),cache['fetched_at']))


def load_cache(conn, name):
    row = conn.execute('SELECT payload,fetched_at FROM source_cache WHERE cache_name=%s',(name,)).fetchone()
    if row is None:
        return None
    payload, fetched_at = row
    if isinstance(payload,dict) and payload.get(_CACHE_MANIFEST_KEY)=='json-text-chunks':
        names = payload.get('parts')
        if not isinstance(names,list) or not names or len(names)!=len(set(names)):
            raise RuntimeError('Invalid chunked source cache manifest')
        namespace = _cache_namespace(name)
        if any(not isinstance(part,str) or not part.startswith(namespace) for part in names):
            raise RuntimeError('Invalid chunked source cache namespace')
        parts = dict(conn.execute('SELECT cache_name,payload FROM source_cache WHERE cache_name=ANY(%s)',(names,)).fetchall())
        if len(parts)!=len(names):
            raise RuntimeError('Incomplete chunked source cache')
        chunks, digest, byte_count = [], hashlib.sha256(), 0
        for part in names:
            data = parts[part].get('data')
            if not isinstance(data,str) or not data.isascii():
                raise RuntimeError('Invalid chunked source cache data')
            digest.update(data.encode('ascii')); byte_count += len(data)
            chunks.append(data)
        if digest.hexdigest()!=payload.get('sha256') or byte_count!=payload.get('serialized_bytes'):
            raise RuntimeError('Chunked source cache checksum mismatch')
        payload = json.loads(''.join(chunks))
    return {'payload':payload, 'fetched_at':_iso(fetched_at)}
