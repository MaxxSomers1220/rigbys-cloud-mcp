"""Required old-key401/new-key-pass HTTP check with test licenses only."""
from test_database import database
from test_gumroad import provider
from test_redeem import redeem_client,submit,parse


def test_rotation_route_revokes_old_and_new_can_call_mcp(redeem_client,provider,database):
    license_key,payload=provider;email=payload['purchase']['email']
    old=parse(submit(redeem_client,license_key,email)).key
    token=parse(redeem_client.get('/redeem')).token
    response=redeem_client.post('/redeem/rotate',data={'license_key':license_key,'email':email,'csrf_token':token})
    assert response.status_code==200
    new=parse(response).key
    assert new and new!=old and response.text.count(new)==1 and old not in response.text
    headers={'Accept':'application/json, text/event-stream','MCP-Protocol-Version':'2025-06-18'}
    body={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'opportunity_search','arguments':{'topic':'rare disease'}}}
    refused=redeem_client.post('/mcp',json=body,headers={**headers,'Authorization':'Bearer '+old})
    assert refused.status_code==401
    allowed=redeem_client.post('/mcp',json=body,headers={**headers,'Authorization':'Bearer '+new})
    assert allowed.status_code==200 and not allowed.json()['result'].get('isError',False)
