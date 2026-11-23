import json
import logging

import httpx
from rigbys_feed.sources import PublicClient, GrantsGov, SourceError
import pytest


def test_grants_pagination_raw_and_detail(tmp_path, caplog):
    calls = []
    def handle(request):
        body = json.loads(request.content)
        calls.append(body)
        if request.url.path.endswith('search2'):
            start = body['startRecordNum']
            data = {'hitCount': 101, 'oppHits': [{'id': str(i+1)} for i in range(start, min(start+100, 101))]}
        else:
            data = {'id': body['opportunityId'], 'synopsis': {'responseDateStr': '2027-01-01-00-00-00'}}
        return httpx.Response(200, json={'errorcode': 0, 'data': data})
    client = PublicClient(tmp_path, httpx.Client(transport=httpx.MockTransport(handle)))
    with caplog.at_level(logging.INFO, logger='rigbys_feed.sources'):
        result = GrantsGov(client).fetch(workers=1)
    assert len(result) == 101
    assert calls[1]['startRecordNum'] == 100
    assert len(list(tmp_path.rglob('*.json'))) == 103
    event = json.loads(caplog.records[-1].getMessage())
    assert event['source'] == 'grants_gov' and event['count'] == 101
    assert event['level'] == 'info'
    assert event['message'] == 'Fetched 101 posted Grants.gov opportunities'


def test_grants_error_is_not_empty_success(tmp_path):
    client = PublicClient(tmp_path, httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json={'errorcode': 1}))))
    with pytest.raises(SourceError):
        GrantsGov(client).fetch()


def test_public_raw_excludes_session_token(tmp_path):
    import json
    client=PublicClient(tmp_path,httpx.Client(transport=httpx.MockTransport(
        lambda r:httpx.Response(200,json={'token':'session-token','data':{'id':1}}))))
    result,ref=client.request('grants_gov','GET','https://example.test')
    assert result['token']=='session-token'
    envelope=json.loads(__import__('pathlib').Path(ref['raw_path']).read_text())
    assert 'token' not in envelope['response']
    assert envelope['response']['data']=={'id':1}


def test_grants_repeated_ids_fail_instead_of_partial_success(tmp_path):
    client=PublicClient(tmp_path,httpx.Client(transport=httpx.MockTransport(
        lambda r:httpx.Response(200,json={'errorcode':0,'data':{'hitCount':2,'oppHits':[{'id':'1'}]}}))))
    with pytest.raises(SourceError,match='unique count'):
        GrantsGov(client).fetch()
