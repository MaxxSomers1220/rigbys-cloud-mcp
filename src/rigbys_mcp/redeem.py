"""Small server-rendered redemption form; no raw credential is cached or logged."""
from functools import partial
from html import escape
import secrets
from urllib.parse import parse_qs

import anyio
from fastapi import APIRouter, Request
from starlette.responses import HTMLResponse

from .gumroad import GumroadVerifier
from .keys import KeyErrorResponse, redeem, rotate

COOKIE='rigbys_redeem_csrf'
MAX_FORM=8192
router=APIRouter()
HEADERS={
    'Cache-Control':'no-store, max-age=0', 'Pragma':'no-cache', 'Expires':'0',
    'Referrer-Policy':'no-referrer', 'X-Content-Type-Options':'nosniff',
    'X-Frame-Options':'DENY',
    'Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
}
TERMS='''<p>$99 one-time MCP pass. Access lasts 90 days from redemption, not purchase.
Paid: 1,000 tool calls/day. Free: 20 searches/day, search only, seven-day-delayed,
with no scores or summaries. No auto-renew. No subscriptions.</p>'''


def page(content,status=200):
    return HTMLResponse('''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Rigby's Cloud access</title>
<style>body{font:17px/1.6 system-ui;max-width:760px;margin:3rem auto;padding:0 1rem;color:#172b32;background:#f5f8f7}
label{display:block;margin-top:1rem}input{display:block;width:95%;padding:.7rem;font:inherit}button{margin-top:1rem;padding:.7rem 1.4rem;font:inherit}
pre,code{overflow-wrap:anywhere;white-space:pre-wrap;background:#e7eeeb;padding:.4rem}a{color:#125f51}</style></head><body><main>
<h1>Rigby's Cloud access</h1>'''+content+TERMS+'</main></body></html>',status_code=status,headers=HEADERS)


def success(issued):
    # Show the credential exactly once. Commands refer to the environment variable
    # and never duplicate a raw key in HTML, URL, redirect, cookie, or session.
    return page('''<h2>Your API key</h2><p>Copy it now and keep it somewhere private.
It cannot be displayed again. If lost, use the rotation option below.</p>
<code id="api-key">'''+escape(issued.raw_key)+'''</code><p>Expires: '''+escape(issued.expires_at.isoformat())+'''</p>
<p>Replace the example key below with the key shown above.</p>
<h2>Connect Codex</h2><pre>export RIGBYS_API_KEY="rgby_live_…"
codex mcp add rigbys-cloud --url https://mcp.rigbyscloud.com/mcp --bearer-token-env-var RIGBYS_API_KEY</pre>
<h2>Connect Claude Code</h2><pre>export RIGBYS_API_KEY="rgby_live_…"
claude mcp add --transport http rigbys-cloud https://mcp.rigbyscloud.com/mcp --header "Authorization: Bearer $RIGBYS_API_KEY" --scope user</pre>
<p>These commands target the production hostname; local testing does not make it live.
<a href="/redeem">Return to access options</a>.</p>''')


async def read_form(request):
    if request.headers.get('content-type','').split(';',1)[0].strip().lower()!='application/x-www-form-urlencoded':
        raise KeyErrorResponse(415,'Submit the access form using the page below.')
    body=b''
    async for chunk in request.stream():
        body+=chunk
        if len(body)>MAX_FORM:raise KeyErrorResponse(413,'The form is too large.')
    try:
        fields=parse_qs(body.decode('utf-8'),keep_blank_values=True,strict_parsing=True,max_num_fields=8)
    except (ValueError,UnicodeError):
        raise KeyErrorResponse(400,'The form could not be read.') from None
    if any(len(values)!=1 for values in fields.values()):
        raise KeyErrorResponse(400,'Submit each form field once.')
    origin=request.headers.get('origin')
    if origin is not None and origin.rstrip('/')!=str(request.base_url).rstrip('/'):
        raise KeyErrorResponse(403,'Reload the access page and submit its form.')
    if request.headers.get('sec-fetch-site')=='cross-site':
        raise KeyErrorResponse(403,'Reload the access page and submit its form.')
    token=fields.get('csrf_token',[''])[0]
    cookie=request.cookies.get(COOKIE,'')
    if not token or len(token)>128 or not cookie or not secrets.compare_digest(token,cookie):
        raise KeyErrorResponse(403,'Reload the access page and submit its form.')
    return {key:values[0] for key,values in fields.items()}


@router.get('/redeem',response_class=HTMLResponse)
async def redeem_page(request:Request):
    token=secrets.token_urlsafe(32)
    response=page('''<p>Redeem your Gumroad MCP-pass license. Use the email on the purchase.</p>
<form method="post" action="/redeem" autocomplete="off">
<input type="hidden" name="csrf_token" value="'''+token+'''">
<label>Gumroad license key<input name="license_key" type="password" required maxlength="512" autocomplete="off"></label>
<label>Purchase email<input name="email" type="email" required maxlength="254" autocomplete="email"></label>
<button type="submit">Redeem pass</button>
<p>Already redeemed? Replace a lost or compromised key below. Your old key stops
working immediately. Rotation does not extend expiry or reset your daily quota.</p>
<button type="submit" formaction="/redeem/rotate">Replace my API key</button></form>''')
    response.set_cookie(COOKIE,token,max_age=900,httponly=True,secure=request.url.scheme=='https',samesite='strict',path='/redeem')
    return response


async def _submit(request, operation):
    try:
        fields=await read_form(request)
        if set(fields)!={'license_key','email','csrf_token'}:
            raise KeyErrorResponse(400,'Complete the license and email fields.')
        verifier=request.app.state.license_verifier
        issued=await anyio.to_thread.run_sync(partial(operation,fields['license_key'],fields['email'],verifier))
        response=success(issued)
    except KeyErrorResponse as exc:
        response=page('<p role="alert">'+escape(exc.message)+'</p><a href="/redeem">Return to the access page</a>',exc.status)
    except Exception:
        # Do not let provider/request/DB exception details expose credentials.
        response=page('<p role="alert">Key service is temporarily unavailable.</p><a href="/redeem">Return to the access page</a>',503)
    response.delete_cookie(COOKIE,path='/redeem')
    return response


@router.post('/redeem',response_class=HTMLResponse)
async def redeem_submit(request:Request):
    return await _submit(request,redeem)


@router.post('/redeem/rotate',response_class=HTMLResponse)
async def rotate_submit(request:Request):
    return await _submit(request,rotate)
