"""Bearer verification and atomic UTC daily quotas; no key issuance or redemption flow."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
import re

import anyio
import psycopg
from starlette.responses import JSONResponse

TOOLS = {'opportunity_search','opportunity_get','opportunity_links','gap_for_topic'}
KEY_PATTERN = re.compile(r'\Argby_(live|free)_[A-Za-z0-9_-]{16,128}\Z')
MAX_BODY = 64 * 1024


@dataclass(frozen=True)
class Principal:
    key_hash: str
    tier: str
    now: datetime


class AccessError(Exception):
    def __init__(self, status, message, retry_after=None):
        self.status, self.message, self.retry_after = status, message, retry_after
        super().__init__(message)


def utcnow():
    return datetime.now(timezone.utc)


def authorize(token, tool_name=None, arguments=None, charge=False, now=None):
    now=(now or utcnow()).astimezone(timezone.utc)
    matched=KEY_PATTERN.fullmatch(token) if isinstance(token,str) else None
    if matched is None:
        raise AccessError(401,'A valid Bearer API key is required')
    digest=hashlib.sha256(token.encode()).hexdigest()
    try:
        with psycopg.connect(os.environ['DATABASE_URL'],autocommit=True) as conn:
            with conn.transaction():
                row=conn.execute('''SELECT k.tier,k.expires_at,k.revoked_at,
                    (SELECT min(redeemed_at) FROM redemptions WHERE api_key_hash=k.key_hash)
                    FROM api_keys k WHERE key_hash=%s FOR SHARE OF k''',(digest,)).fetchone()
                if row is None or row[2] is not None or row[0] != ('paid' if matched[1]=='live' else 'free'):
                    raise AccessError(401,'Key is invalid or revoked')
                tier,expires,_,redeemed=row
                if tier=='paid':
                    if expires is None or redeemed is None or redeemed>now:
                        raise AccessError(401,'Key is not active')
                    # Rotating a key must not restart its access clock.
                    expires=min(expires,redeemed+timedelta(days=90))
                if expires is not None and expires<=now:
                    raise AccessError(401,'Key expired — renew at mcp.rigbyscloud.com/redeem')
                if tool_name is not None and tier=='free':
                    if tool_name!='opportunity_search' or (arguments or {}).get('min_gap_score') is not None:
                        raise AccessError(403,'Paid pass required — access information: https://mcp.rigbyscloud.com/redeem')
                if charge:
                    cap=1000 if tier=='paid' else 20
                    used=conn.execute('''INSERT INTO rate_limit_counters(key_hash,day,calls)
                        VALUES (%s,%s,1) ON CONFLICT(key_hash,day) DO UPDATE
                        SET calls=rate_limit_counters.calls+1
                        WHERE rate_limit_counters.calls<%s RETURNING calls''',
                        (digest,now.date(),cap)).fetchone()
                    if used is None:
                        midnight=datetime.combine(now.date()+timedelta(days=1),datetime.min.time(),timezone.utc)
                        raise AccessError(429,'Daily call limit reached',max(1,math.ceil((midnight-now).total_seconds())))
    except (psycopg.Error,KeyError):
        raise AccessError(503,'Service temporarily unavailable') from None
    return Principal(digest,tier,now)


class BearerMiddleware:
    """Pure ASGI: authenticates every MCP request and checks each tool attempt.

    MCP is stateless; a session identifier never grants access. The verified
    principal is attached to this HTTP scope, not a process-wide mutable cache.
    """
    def __init__(self, app):
        self.app=app

    async def __call__(self, scope, receive, send):
        if scope['type']!='http' or scope.get('path','').rstrip('/')!='/mcp':
            return await self.app(scope,receive,send)
        if scope.get('path')=='/mcp/':
            # Canonicalize before charging so a 307 retry cannot count one call twice.
            scope={**scope, 'path':'/mcp', 'raw_path':b'/mcp'}
        try:
            auth=[v for k,v in scope.get('headers',[]) if k.lower()==b'authorization']
            if len(auth)!=1:
                raise AccessError(401,'Authorization: Bearer <API key> is required')
            try:
                scheme,token=auth[0].decode('ascii').split(' ',1)
            except (ValueError,UnicodeError):
                raise AccessError(401,'Authorization: Bearer <API key> is required') from None
            if scheme.lower()!='bearer' or not token or token!=token.strip():
                raise AccessError(401,'Authorization: Bearer <API key> is required')
            principal=await anyio.to_thread.run_sync(authorize,token)
            body=b''
            if scope['method']=='POST':
                while True:
                    message=await receive()
                    if message['type']=='http.disconnect': return
                    body+=message.get('body',b'')
                    if len(body)>MAX_BODY: raise AccessError(413,'MCP request is too large')
                    if not message.get('more_body',False):break
                try:
                    payload=json.loads(body)
                except (ValueError,UnicodeError,RecursionError):
                    raise AccessError(400,'Invalid JSON request') from None
                if not isinstance(payload,dict):
                    raise AccessError(400,'JSON-RPC batch requests are not supported')
                if payload.get('method')=='tools/call':
                    params=payload.get('params')
                    if not isinstance(params,dict) or not isinstance(params.get('name'),str):
                        raise AccessError(400,'A tool name is required')
                    arguments=params.get('arguments',{})
                    if not isinstance(arguments,dict):raise AccessError(400,'Tool arguments must be an object')
                    principal=await anyio.to_thread.run_sync(
                        lambda:authorize(token,params['name'],arguments,True))
                sent=False
                original_receive=receive
                async def replay():
                    nonlocal sent
                    if not sent:
                        sent=True
                        return {'type':'http.request','body':body,'more_body':False}
                    return await original_receive()
                receive=replay
            scope['rigbys_principal']=principal
            return await self.app(scope,receive,send)
        except AccessError as exc:
            headers={}
            if exc.status==401:headers['WWW-Authenticate']='Bearer'
            if exc.retry_after is not None:headers['Retry-After']=str(exc.retry_after)
            return await JSONResponse({'error':exc.message},status_code=exc.status,headers=headers)(scope,receive,send)
