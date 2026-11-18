"""Local FastAPI/FastMCP service with pass redemption; no deployment."""
from datetime import date
from functools import partial
import anyio
import os
from fastapi import FastAPI
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
import uvicorn
from .repository import Repository, QueryError
from .auth import BearerMiddleware
from .redeem import router as redeem_router
from .gumroad import GumroadVerifier
from .health import router as health_router
from .origin import configured_public_origin
from . import SERVER_VERSION
from fastmcp.server.dependencies import get_http_request

INSTRUCTIONS = """Rigby's Cloud Grants Feed #1: public US-federal opportunities from Grants.gov,
NIH RePORTER awards and OpenAlex papers only. Read-only, four tools. Always show
Grants.gov source URL and deadline; dates may be date-only or rolling, so check
source requirements. Show feed_generated_at and source timestamps; never present
stale data as fresh. Preserve score_evidence and coverage: neutral insufficient-data
scores are placeholders, not funding-gap findings. Scores are versioned descriptive
proxies, never predictions of success or proof of neglect. Missing research links
mean missing coverage, not no funding. Broad FOA/award-core paper associations do
not establish current-opportunity funding or topic relevance. Free search uses a
real snapshot at least seven days old with no scores or summaries; other tools
require a paid pass. No trials, patents, global coverage, subscriptions, write
actions or bulk-dump tools. Never invent opportunities, deadlines, amounts or links.
"""
ANNOTATIONS = ToolAnnotations(readOnlyHint=True, destructiveHint=False,
                              idempotentHint=True, openWorldHint=False)


def create_app():
    public_origin = configured_public_origin()
    if not os.environ.get('DATABASE_URL'):
        raise RuntimeError('DATABASE_URL must be supplied through the environment')
    repository = Repository()
    def principal():
        verified=get_http_request().scope.get('rigbys_principal')
        if verified is None:raise ToolError('Authorization is required')
        return verified
    mcp = FastMCP('rigbys-cloud', version=SERVER_VERSION, instructions=INSTRUCTIONS, mask_error_details=True)

    @mcp.tool(annotations=ANNOTATIONS)
    async def opportunity_search(topic: str, sponsor: str | None = None,
                                 deadline_before: date | None = None, deadline_after: date | None = None,
                                 min_gap_score: int | None = None, limit: int = 10) -> dict:
        """Search public US-federal opportunities; preserve evidence flags and cite source URLs and dates."""
        try:
            caller=principal()
            if caller.tier=='free':
                return await anyio.to_thread.run_sync(partial(repository.search_free, topic, sponsor,
                    deadline_before,deadline_after,limit,caller.now))
            return await anyio.to_thread.run_sync(partial(repository.search, topic, sponsor,
                deadline_before,deadline_after,min_gap_score,limit))
        except QueryError as exc:
            raise ToolError(str(exc)) from None

    @mcp.tool(annotations=ANNOTATIONS)
    async def opportunity_get(opportunity_id: str) -> dict:
        """Get a full source-backed opportunity, preserving all layers, coverage and score evidence."""
        try:
            if principal().tier!='paid':raise ToolError('Paid pass required')
            return await anyio.to_thread.run_sync(partial(repository.get, opportunity_id))
        except QueryError as exc:
            raise ToolError(str(exc)) from None

    @mcp.tool(annotations=ANNOTATIONS)
    async def opportunity_links(opportunity_id: str) -> dict:
        """Read confirmed award and paper edges with confidence and source URLs; no scores or summaries."""
        try:
            if principal().tier!='paid':raise ToolError('Paid pass required')
            return await anyio.to_thread.run_sync(partial(repository.links, opportunity_id))
        except QueryError as exc:
            raise ToolError(str(exc)) from None

    @mcp.tool(annotations=ANNOTATIONS)
    async def gap_for_topic(topic: str, window_months: int = 12) -> dict:
        """Describe topic portfolios with source counts and explicit thin-evidence limitations."""
        try:
            if principal().tier!='paid':raise ToolError('Paid pass required')
            return await anyio.to_thread.run_sync(partial(repository.gap, topic, window_months))
        except QueryError as exc:
            raise ToolError(str(exc)) from None

    http = mcp.http_app(path='/mcp', transport='streamable-http', stateless_http=True, json_response=True)
    app = FastAPI(lifespan=http.lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.public_origin=public_origin
    app.state.license_verifier=GumroadVerifier()
    app.include_router(redeem_router)
    app.include_router(health_router)
    app.mount('/', http)
    app.add_middleware(BearerMiddleware)
    return app


def main():
    uvicorn.run('rigbys_mcp.app:create_app', factory=True, host=os.environ.get('HOST','127.0.0.1'),
                port=int(os.environ.get('PORT','8000')), access_log=False,
                proxy_headers=True,
                forwarded_allow_ips=os.environ.get('FORWARDED_ALLOW_IPS','127.0.0.1'))
