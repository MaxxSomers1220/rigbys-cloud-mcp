"""Real local HTTP/MCP adversarial checks with synthetic keys and isolated Postgres.

Tokens are generated at runtime, kept in the process environment, and never
represent sales or production credentials. No redemption flow is implemented.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import secrets
import socket
import threading
import time
from types import SimpleNamespace

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
import pytest
import uvicorn

from mcp_fixtures import AS_OF, EXPECTED_RARE_DISEASE, seed_feed
from test_database import database  # noqa: F401 -- isolated PostgreSQL fixture

BASE_TIME = datetime(AS_OF.year, AS_OF.month, AS_OF.day, 12, tzinfo=timezone.utc)
HEADERS = {'Accept':'application/json, text/event-stream', 'MCP-Protocol-Version':'2025-06-18'}


def rpc(name='opportunity_search', arguments=None, identifier=1):
    return {'jsonrpc':'2.0','id':identifier,'method':'tools/call',
            'params':{'name':name,'arguments':arguments if arguments is not None else {'topic':'rare disease'}}}


def payload(response):
    """Decode the actual MCP result, accepting SDK structured/text encodings."""
    document = response.json() if isinstance(response,httpx.Response) else response.model_dump(by_alias=True)
    result = document.get('result',document)
    assert not result.get('isError'), 'MCP unexpectedly reported a tool error'
    value = result.get('structuredContent')
    if value is None:
        blocks = result.get('content',[])
        value = json.loads(next(block['text'] for block in blocks if block.get('type')=='text'))
    if isinstance(value,dict) and set(value)=={'result'} and isinstance(value['result'],dict):
        value = value['result']
    return value


def token_header(token):
    return {'Authorization':'Bearer '+token}


def assert_plain_error(response,status):
    assert response.status_code==status
    assert response.headers['content-type'].startswith('application/json')
    assert isinstance(response.json().get('error'),str)
    assert not any(marker in response.text for marker in ('Traceback','postgresql://','psycopg','key_hash','@example.test'))


def assert_free_fields(value):
    if isinstance(value,dict):
        for key,item in value.items():
            assert 'score' not in key.lower() and 'summary' not in key.lower()
            assert key not in {'methodology_version','linked_awards','linked_papers','research_coverage'}
            assert_free_fields(item)
    elif isinstance(value,list):
        for item in value:
            assert_free_fields(item)


@pytest.fixture
def service(database,monkeypatch):
    from rigbys_mcp import auth,aggregation
    from rigbys_mcp.app import create_app
    monkeypatch.setenv('DATABASE_URL',database.info.dsn)
    clock={'now':BASE_TIME}
    monkeypatch.setattr(auth,'utcnow',lambda:clock['now'])
    original_as_date=aggregation._as_date
    monkeypatch.setattr(aggregation,'_as_date',lambda value:clock['now'].date() if value is None else original_as_date(value))
    seed_feed(database)
    tokens,hashes={},{}
    def add(label,tier='paid',prefix=None,expires=None,revoked=None,redemption=None,short=False):
        prefix=prefix or ('rgby_live_' if tier=='paid' else 'rgby_free_')
        token=prefix+('x' if short else secrets.token_urlsafe(32))
        monkeypatch.setenv('RIGBYS_HTTP_TEST_'+label.upper(),token)
        digest=hashlib.sha256(token.encode()).hexdigest()
        tokens[label],hashes[label]=token,digest
        expiration=expires if expires is not None else (BASE_TIME+timedelta(days=80) if tier=='paid' else None)
        database.execute('''INSERT INTO api_keys(key_hash,key_prefix,tier,email,expires_at,created_at,revoked_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s)''',
            (digest,token[:12],tier,'synthetic-http-test@example.test',expiration,BASE_TIME-timedelta(days=1),revoked))
        if tier=='paid':
            database.execute('''INSERT INTO redemptions(license_key_hash,api_key_hash,redeemed_at,gumroad_sale_ref)
                VALUES (%s,%s,%s,%s)''',
                (hashlib.sha256(secrets.token_bytes(32)).hexdigest(),digest,
                 redemption if redemption is not None else BASE_TIME-timedelta(days=10),
                 'synthetic-local-test-not-a-sale'))
    add('paid');add('free','free')
    add('expired',expires=BASE_TIME-timedelta(microseconds=1))
    add('revoked',revoked=BASE_TIME-timedelta(seconds=1))
    add('tier_mismatch',prefix='rgby_free_')
    add('short',short=True)
    add('redemption_expired',expires=BASE_TIME+timedelta(days=80),redemption=BASE_TIME-timedelta(days=91))
    app=create_app()
    listener=socket.socket();listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    listener.bind(('127.0.0.1',0));listener.listen(128)
    address='http://127.0.0.1:'+str(listener.getsockname()[1])
    server=uvicorn.Server(uvicorn.Config(app,log_level='critical',access_log=False,lifespan='on'))
    thread=threading.Thread(target=server.run,kwargs={'sockets':[listener]},daemon=True)
    thread.start()
    deadline=time.monotonic()+15
    while not server.started and thread.is_alive() and time.monotonic()<deadline:
        time.sleep(0.01)
    assert server.started,'Local ASGI server failed to start'
    try:
        with httpx.Client(base_url=address,headers=HEADERS,timeout=30) as client:
            yield SimpleNamespace(client=client,url=address+'/mcp',db=database,
                                  tokens=tokens,hashes=hashes,clock=clock)
    finally:
        server.should_exit=True;thread.join(timeout=15);listener.close()
        assert not thread.is_alive(),'Local ASGI server failed to stop'


def counter(service,label):
    row=service.db.execute('SELECT calls FROM rate_limit_counters WHERE key_hash=%s AND day=%s',
                           (service.hashes[label],service.clock['now'].date())).fetchone()
    return row[0] if row else 0


def test_http_auth_rejects_missing_malformed_unknown_expired_revoked_and_short_keys(service):
    client=service.client
    assert_plain_error(client.post('/mcp',json=rpc()),401)
    for label in ('expired','revoked','tier_mismatch','short','redemption_expired'):
        assert_plain_error(client.post('/mcp',json=rpc(),headers=token_header(service.tokens[label])),401)
    unknown='rgby_live_'+secrets.token_urlsafe(32)
    assert_plain_error(client.post('/mcp',json=rpc(),headers=token_header(unknown)),401)
    for authorization in ('Basic ignored','Bearer','', 'Bearer  '+service.tokens['paid']):
        assert_plain_error(client.post('/mcp',json=rpc(),headers={'Authorization':authorization}),401)
    duplicate=[('Authorization','Bearer '+service.tokens['paid']),('authorization','Bearer '+service.tokens['free'])]
    assert_plain_error(client.post('/mcp',json=rpc(),headers=duplicate),401)
    for method in ('GET','DELETE'):
        assert_plain_error(client.request(method,'/mcp'),401)
    assert_plain_error(client.post('/mcp?api_key='+unknown,json=rpc()),401)
    assert counter(service,'paid')==0


def test_real_sdk_lists_four_tools_and_calls_all_four_paid_without_charging_handshake(service):
    expected=service.db.execute("SELECT record FROM opportunities WHERE opportunity_id='fixture-0001'").fetchone()[0]
    async def exercise():
        async with streamablehttp_client(service.url,headers=token_header(service.tokens['paid']),terminate_on_close=False) as (read,write,_):
            async with ClientSession(read,write) as session:
                initialized=await session.initialize()
                assert initialized.serverInfo.name=='rigbys-cloud'
                assert initialized.serverInfo.version=='1.0.0'
                listed=await session.list_tools()
                assert {tool.name for tool in listed.tools}=={'opportunity_search','opportunity_get','opportunity_links','gap_for_topic'}
                assert counter(service,'paid')==0
                search=payload(await session.call_tool('opportunity_search',{'topic':'rare disease','limit':25}))
                assert len(search['opportunities'])==8
                assert sum(x['score_evidence']['status']=='insufficient_data_neutral_placeholder'
                           for x in search['opportunities'])==2
                record=payload(await session.call_tool('opportunity_get',{'opportunity_id':'fixture-0001'}))
                assert record==expected
                links=payload(await session.call_tool('opportunity_links',{'opportunity_id':'fixture-0001'}))
                assert len(links['edges'])==4
                assert all('join_confidence' in e and 'target_url' in e for e in links['edges'])
                gap=payload(await session.call_tool('gap_for_topic',{'topic':'rare disease'}))
                for field in ('open_opportunity_count','awarded_grant_count','paper_count',
                              'median_growth_score','median_momentum_score','median_novelty_score','median_gap_score'):
                    assert gap[field]==EXPECTED_RARE_DISEASE[field]
    asyncio.run(exercise())
    assert counter(service,'paid')==4


def test_free_paid_tool_and_score_filter_refusals_do_not_consume_search_quota(service):
    headers=token_header(service.tokens['free'])
    for name,args in [('opportunity_get',{'opportunity_id':'fixture-0001'}),
                      ('opportunity_links',{'opportunity_id':'fixture-0001'}),
                      ('gap_for_topic',{'topic':'rare disease'}),
                      ('opportunity_search',{'topic':'rare disease','min_gap_score':0})]:
        response=service.client.post('/mcp',json=rpc(name,args),headers=headers)
        assert_plain_error(response,403)
        assert 'paid' in response.text.lower()
    assert counter(service,'free')==0
    response=service.client.post('/mcp',json=rpc(),headers=headers)
    assert response.status_code==200
    free=payload(response)
    assert free['status']=='delayed_feed_unavailable'
    assert free['opportunities']==[] and free['feed_generated_at'] is None
    assert_free_fields(free)
    assert counter(service,'free')==1


def test_genuine_capture_ages_exactly_seven_days_and_never_leaks_paid_fields(service):
    captured,generated=service.db.execute('SELECT captured_at,feed_generated_at FROM free_feed_snapshots ORDER BY snapshot_id DESC LIMIT 1').fetchone()
    headers=token_header(service.tokens['free'])
    service.clock['now']=max(captured,generated)+timedelta(days=7)-timedelta(microseconds=1)
    fresh=payload(service.client.post('/mcp',json=rpc(),headers=headers))
    assert fresh['status']=='delayed_feed_unavailable'
    service.clock['now']=max(captured,generated)+timedelta(days=7)
    response=service.client.post('/mcp',json=rpc(arguments={'topic':'rare disease','limit':25}),headers=headers)
    assert response.status_code==200
    old=payload(response)
    assert old['status']=='delayed_snapshot' and len(old['opportunities'])==8
    assert_free_fields(old)
    for record in old['opportunities']:
        assert datetime.fromisoformat(record['feed_generated_at'])<=service.clock['now']-timedelta(days=7)
        assert record['source_refs']
    # The paid source record remains scored and summarized; snapshot projection did not mutate it.
    current=service.db.execute("SELECT record FROM opportunities WHERE opportunity_id='fixture-0001'").fetchone()[0]
    assert current['summary_short'] and current['score_evidence']['status']=='descriptive_proxy'


def test_quota_twenty_free_and_one_thousand_paid_with_http_retry_after(service):
    free_headers=token_header(service.tokens['free'])
    for _ in range(20):
        assert service.client.post('/mcp',json=rpc(),headers=free_headers).status_code==200
    blocked=service.client.post('/mcp',json=rpc(),headers=free_headers)
    assert_plain_error(blocked,429)
    assert int(blocked.headers['Retry-After'])==int((datetime.combine(BASE_TIME.date()+timedelta(days=1),datetime.min.time(),timezone.utc)-BASE_TIME).total_seconds())
    assert counter(service,'free')==20
    service.db.execute('INSERT INTO rate_limit_counters(key_hash,day,calls) VALUES (%s,%s,999)',
                       (service.hashes['paid'],BASE_TIME.date()))
    def call(_):
        with httpx.Client(headers=HEADERS,timeout=30) as client:
            return client.post(service.url,json=rpc(),headers=token_header(service.tokens['paid']))
    with ThreadPoolExecutor(max_workers=10) as pool:
        results=list(pool.map(call,range(20)))
    assert sum(r.status_code==200 for r in results)==1
    assert sum(r.status_code==429 for r in results)==19
    assert counter(service,'paid')==1000
    assert all(int(r.headers['Retry-After'])>0 for r in results if r.status_code==429)


def test_malformed_batch_and_oversized_chunked_requests_rejected_before_charge(service):
    headers={**token_header(service.tokens['paid']),'Content-Type':'application/json'}
    for body,status in [(b'{broken',400),(b'[]',400),(b'[{},{}]',400),(b'null',400)]:
        assert_plain_error(service.client.post('/mcp',content=body,headers=headers),status)
    # A generator omits Content-Length and exercises actual chunked HTTP transfer.
    chunks=(b'x'*chunk for chunk in (30_000,30_000,10_000))
    assert_plain_error(service.client.post('/mcp',content=chunks,headers=headers),413)
    assert counter(service,'paid')==0
    # Recognized tool-call attempts consume quota even if the SDK rejects a tool or its arguments.
    response=service.client.post('/mcp',json=rpc('unknown_tool',{}),headers=token_header(service.tokens['paid']))
    assert response.status_code==200
    response=service.client.post('/mcp',json=rpc(arguments={'topic':'rare disease','limit':0}),headers=token_header(service.tokens['paid']))
    assert response.status_code==200
    assert counter(service,'paid')==2


def test_revocation_rechecked_and_principal_never_follows_session_header(service):
    paid_headers={**token_header(service.tokens['paid']),'Mcp-Session-Id':'same-untrusted-session'}
    assert service.client.post('/mcp',json=rpc(),headers=paid_headers).status_code==200
    free_headers={**token_header(service.tokens['free']),'Mcp-Session-Id':'same-untrusted-session'}
    assert_plain_error(service.client.post('/mcp',json=rpc('opportunity_get',{'opportunity_id':'fixture-0001'}),headers=free_headers),403)
    service.db.execute('UPDATE api_keys SET revoked_at=%s WHERE key_hash=%s',
                       (BASE_TIME,service.hashes['paid']))
    assert_plain_error(service.client.post('/mcp',json=rpc(),headers=paid_headers),401)
    assert counter(service,'paid')==1


def test_concurrent_free_and_paid_searches_keep_principals_separate(service):
    def call(index):
        label='paid' if index%2 else 'free'
        with httpx.Client(headers=HEADERS,timeout=30) as client:
            response=client.post(service.url,json=rpc(),headers=token_header(service.tokens[label]))
        assert response.status_code==200
        return label,payload(response)
    with ThreadPoolExecutor(max_workers=10) as pool:
        results=list(pool.map(call,range(20)))
    for label,result in results:
        if label=='free':
            assert result['status']=='delayed_feed_unavailable'
            assert result['opportunities']==[]
            assert_free_fields(result)
        else:
            assert len(result['opportunities'])==8
            assert all('score_evidence' in record and 'summary_short' in record
                       for record in result['opportunities'])
    assert counter(service,'free')==counter(service,'paid')==10


def test_trailing_slash_is_not_a_redirect_or_double_charge_and_later_phase_routes_absent(service):
    response=service.client.post('/mcp/',json=rpc(),headers=token_header(service.tokens['paid']),
                                 follow_redirects=False)
    assert response.status_code==200
    assert 'location' not in response.headers
    assert len(payload(response)['opportunities'])==8
    assert counter(service,'paid')==1
    for path in ('/redeem','/health','/sse','/docs'):
        assert service.client.get(path,follow_redirects=False).status_code==404
    assert counter(service,'paid')==1
