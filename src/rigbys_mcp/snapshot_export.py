"""Download the current paid feed as one gzip-compressed JSON attachment."""
from contextlib import AsyncExitStack
from functools import partial

import anyio
import psycopg
from fastapi import APIRouter, Request
from starlette.responses import JSONResponse, Response, StreamingResponse

from rigbys_feed.snapshot_export import open_current_export

from .auth import AccessError, access_error_response, authorize, bearer_token

router = APIRouter()
_PRIVATE_HEADERS = {'Cache-Control': 'private, no-store', 'Vary': 'Authorization'}


class SnapshotDownload(Response):
    async def __call__(self, scope, receive, send):
        # Keep the same database view for headers and body, even if a build
        # rotates the stored export during this download.
        async with AsyncExitStack() as stack:
            try:
                export = await stack.enter_async_context(open_current_export())
            except psycopg.Error:
                export = None
            if export is None:
                response = JSONResponse(
                    {'error': 'Snapshot export is temporarily unavailable'},
                    status_code=503, headers=_PRIVATE_HEADERS,
                )
            else:
                response = StreamingResponse(export.chunks, media_type='application/gzip', headers={
                    **_PRIVATE_HEADERS,
                    'Content-Disposition': 'attachment; filename="rigbys-cloud-feed.json.gz"',
                    'Content-Length': str(export.size_bytes),
                    'X-Feed-Generated-At': export.feed_generated_at,
                    'X-Feed-Record-Count': str(export.record_count),
                })
            await response(scope, receive, send)


@router.get('/snapshot-export')
async def download_snapshot(request: Request):
    try:
        token = bearer_token(request.scope)
        await anyio.to_thread.run_sync(partial(authorize, token, 'snapshot_export', charge=True))
    except AccessError as error:
        response = access_error_response(error)
        response.headers.update(_PRIVATE_HEADERS)
        return response
    return SnapshotDownload()
