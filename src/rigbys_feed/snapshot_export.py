"""Persist one gzip stream per retained feed and serve it from PostgreSQL."""
from collections.abc import AsyncIterator, Iterable, Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timezone
import json
import os
import zlib

from psycopg import AsyncConnection


_CHUNK_BYTES = 1024 * 1024


@dataclass(frozen=True)
class CurrentExport:
    feed_generated_at: str
    record_count: int
    size_bytes: int
    chunks: AsyncIterator[bytes]


def _gzip_parts(conn, generated_at: str, record_count: int) -> Iterator[bytes]:
    compressor = zlib.compressobj(level=6, wbits=31)
    metadata = json.dumps({'feed_generated_at': generated_at, 'record_count': record_count},
                          separators=(',', ':')).encode('utf-8')
    yield compressor.compress(metadata[:-1] + b',"opportunities":[')

    records_written = 0
    with conn.cursor(name='snapshot_export_records', binary=True) as rows:
        rows.itersize = 4
        rows.execute('''SELECT convert_to(record::text, 'UTF8') FROM opportunities
                        ORDER BY opportunity_id COLLATE "C"''')
        for (record,) in rows:
            if records_written:
                yield compressor.compress(b',')
            yield compressor.compress(record)
            records_written += 1

    if records_written != record_count:
        raise RuntimeError('Snapshot export record count changed during publication')
    yield compressor.compress(b']}')
    yield compressor.flush()


def _fixed_chunks(parts: Iterable[bytes]) -> Iterator[bytes]:
    pending = bytearray()
    for fragment in parts:
        data = memoryview(fragment)
        while data:
            length = min(_CHUNK_BYTES - len(pending), len(data))
            pending.extend(data[:length])
            data = data[length:]
            if len(pending) == _CHUNK_BYTES:
                yield bytes(pending)
                pending.clear()
    if pending:
        yield bytes(pending)


def publish_current_export(conn, run_id: int) -> None:
    """Write and rotate the artifact inside the feed publication transaction."""
    generated_at, record_count = conn.execute('''SELECT feed_generated_at,
        (SELECT count(*) FROM opportunities) FROM feed_runs
        WHERE run_id = %s AND status = 'success' ''', (run_id,)).fetchone()
    timestamp = generated_at.astimezone(timezone.utc).isoformat()
    chunk_count = size_bytes = 0

    conn.execute("DELETE FROM snapshot_exports WHERE slot = 'previous'")
    conn.execute("UPDATE snapshot_exports SET slot = 'previous' WHERE slot = 'current'")
    for index, data in enumerate(_fixed_chunks(_gzip_parts(conn, timestamp, record_count))):
        conn.execute('''INSERT INTO snapshot_export_chunks (run_id, chunk_index, data)
                        VALUES (%s, %s, %s)''', (run_id, index, data))
        chunk_count += 1
        size_bytes += len(data)
    conn.execute('''INSERT INTO snapshot_exports (slot, run_id, record_count, size_bytes, chunk_count)
                    VALUES ('current', %s, %s, %s, %s)''',
                 (run_id, record_count, size_bytes, chunk_count))


async def _read_chunks(rows, chunk_count: int, size_bytes: int) -> AsyncIterator[bytes]:
    chunks_read = bytes_read = 0
    async for index, data in rows:
        if index != chunks_read or index >= chunk_count or bytes_read + len(data) > size_bytes:
            raise RuntimeError('Invalid snapshot export chunk sequence')
        chunks_read += 1
        bytes_read += len(data)
        yield data
    if chunks_read != chunk_count or bytes_read != size_bytes:
        raise RuntimeError('Incomplete snapshot export')


@asynccontextmanager
async def open_current_export() -> AsyncIterator[CurrentExport | None]:
    """Keep the manifest and stream pinned to one database snapshot until exit."""
    async with await AsyncConnection.connect(os.environ['DATABASE_URL'], autocommit=True) as conn:
        async with conn.transaction():
            await conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            # A builder on the prior release may publish without a matching export.
            manifest = await conn.execute('''SELECT export.run_id, run.feed_generated_at,
                export.record_count, export.size_bytes, export.chunk_count
                FROM snapshot_exports AS export JOIN feed_runs AS run USING (run_id)
                WHERE export.slot = 'current' AND export.run_id = (
                    SELECT run_id FROM feed_runs WHERE status = 'success'
                    ORDER BY run_id DESC LIMIT 1
                )''')
            row = await manifest.fetchone()
            if row is None:
                yield None
                return

            run_id, generated_at, record_count, size_bytes, chunk_count = row
            async with conn.cursor(name='snapshot_export_download', binary=True) as rows:
                rows.itersize = 2
                await rows.execute('''SELECT chunk_index, data FROM snapshot_export_chunks
                                      WHERE run_id = %s ORDER BY chunk_index''', (run_id,))
                yield CurrentExport(generated_at.astimezone(timezone.utc).isoformat(), record_count,
                                    size_bytes, _read_chunks(rows, chunk_count, size_bytes))
