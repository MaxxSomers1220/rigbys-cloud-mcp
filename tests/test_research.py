"""Research fetchers preserve source IDs and fail instead of truncating."""
import json

import httpx
import pytest

from rigbys_feed.research import OpenAlex, Reporter, fetch_research
from rigbys_feed.sources import PublicClient, SourceError


def public_client(tmp_path, handler):
    return PublicClient(tmp_path, httpx.Client(transport=httpx.MockTransport(handler)))


def award(i):
    return {
        'appl_id': i,
        'project_num': f'1R01AI{i:06d}-01',
        'core_project_num': f'R01AI{i:06d}',
        'opportunity_number': 'PA-25-301',
        'fiscal_year': 2026,
        'project_detail_url': f'https://reporter.nih.gov/project-details/{i}',
    }


def test_reporter_awards_pagination_and_raw_refs(tmp_path):
    offsets = []

    def handle(request):
        body = json.loads(request.content)
        assert body['criteria']['foa'] == ['PA-25-301']
        assert body['criteria']['fiscal_years'] == [2026]
        offsets.append(body['offset'])
        start = body['offset']
        return httpx.Response(200, json={
            'meta': {'total': 501, 'offset': start, 'limit': 500},
            'results': [award(i) for i in range(start, min(start + 500, 501))],
        })

    rows = Reporter(public_client(tmp_path, handle)).awards(['PA-25-301'], fiscal_years=[2026])
    assert len(rows) == 501
    assert offsets == [0, 500]
    assert rows[-1]['record']['appl_id'] == 500
    assert rows[-1]['ref']['source'] == 'nih_reporter'
    assert len(list(tmp_path.rglob('*.json'))) == 2


def test_reporter_missing_page_is_failure(tmp_path):
    def handle(request):
        body = json.loads(request.content)
        return httpx.Response(200, json={
            'meta': {'total': 501, 'offset': body['offset'], 'limit': 500},
            'results': [award(i) for i in range(500)] if body['offset'] == 0 else [],
        })

    with pytest.raises(SourceError):
        Reporter(public_client(tmp_path, handle)).awards(['PA-25-301'], fiscal_years=[2026])


def test_reporter_publications_paginate(tmp_path):
    offsets = []

    def handle(request):
        assert request.url.path.endswith('/publications/search')
        body = json.loads(request.content)
        assert body['criteria']['core_project_nums'] == ['R01AI000001']
        start = body['offset']
        offsets.append(start)
        return httpx.Response(200, json={
            'meta': {'total': 501, 'offset': start, 'limit': 500},
            'results': [{'coreproject': 'R01AI000001', 'pmid': 1000 + i, 'applid': 1}
                        for i in range(start, min(start + 500, 501))],
        })

    rows = Reporter(public_client(tmp_path, handle)).publications(['R01AI000001'])
    assert offsets == [0, 500]
    assert len(rows) == 501
    assert rows[-1]['record']['pmid'] == 1500


def test_openalex_batches_101_pmids_and_keeps_source_ids(tmp_path):
    batches = []

    def handle(request):
        assert request.url.path == '/works'
        values = request.url.params['filter'].split(':', 1)[1].split('|')
        batches.append(values)
        return httpx.Response(200, json={
            'meta': {'count': len(values), 'next_cursor': None},
            'results': [{'id': f'https://openalex.org/W{v}',
                         'ids': {'pmid': f'https://pubmed.ncbi.nlm.nih.gov/{v}'}}
                        for v in values],
        })

    rows = OpenAlex(public_client(tmp_path, handle)).papers([str(i) for i in range(1, 102)])
    assert sorted(map(len, batches)) == [1, 100]
    assert len(rows) == 101
    assert {r['record']['id'] for r in rows} == {f'https://openalex.org/W{i}' for i in range(1, 102)}


def test_empty_identifiers_do_not_fetch_unscoped_data(tmp_path):
    def handle(request):
        pytest.fail('empty identifiers must not trigger an unfiltered source fetch')

    client = public_client(tmp_path, handle)
    assert Reporter(client).awards([], fiscal_years=[2026]) == []
    assert Reporter(client).publications([]) == []
    assert OpenAlex(client).papers([]) == []


def test_full_exact_id_research_chain(tmp_path):
    def handle(request):
        if request.url.host == 'api.openalex.org':
            assert request.url.params['filter'] == 'awards.funder_award_id:R01AI145687'
            return httpx.Response(200, json={
                'meta': {'count': 1, 'next_cursor': None},
                'results': [{'id': 'https://openalex.org/W3114507428',
                             'ids': {'pmid': 'https://pubmed.ncbi.nlm.nih.gov/33417835'},
                             'awards': [{'funder_award_id': 'R01AI145687'}]}],
            })
        body = json.loads(request.content)
        if request.url.path.endswith('/projects/search'):
            assert body['criteria']['foa'] == ['PA-25-301']
            rows = [dict(award(11381062), project_num='5R01AI145687-07',
                         core_project_num='R01AI145687')]
        else:
            assert body['criteria']['core_project_nums'] == ['R01AI145687']
            rows = [{'coreproject': 'R01AI145687', 'pmid': 33417835, 'applid': 11381062}]
        return httpx.Response(200, json={'meta': {'total': 1, 'offset': 0, 'limit': 500}, 'results': rows})

    grants = [{'record': {'id': 357812, 'opportunityNumber': 'PA-25-301',
                          'owningAgencyCode': 'HHS-NIH11',
                          'synopsis': {'agencyCode': 'HHS-NIH11'}},
               'ref': {'source': 'grants_gov'}}]
    awards, publications, papers, coverage = fetch_research(public_client(tmp_path, handle), grants,
                                                          fiscal_years=[2026])
    assert awards[0]['record']['opportunity_number'] == grants[0]['record']['opportunityNumber']
    assert publications == []
    assert papers[0]['record']['awards'][0]['funder_award_id'] == awards[0]['record']['core_project_num']
    assert '10,000' in coverage['publication_scope']
    assert coverage


def test_reporter_splits_identifier_groups_above_api_cap(tmp_path):
    queried = []

    def handle(request):
        body = json.loads(request.content)
        ids = body['criteria']['foa']
        queried.append(ids)
        if len(ids) == 2:
            return httpx.Response(200, json={'meta': {'total': 15000}, 'results': []})
        row = dict(award(1 if ids[0] == 'PA-25-301' else 2), opportunity_number=ids[0])
        return httpx.Response(200, json={'meta': {'total': 1}, 'results': [row]})

    rows = Reporter(public_client(tmp_path, handle)).awards(['PA-25-301', 'PA-25-302'], [2026])
    assert len(rows) == 2
    assert len(queried) == 3
    assert {r['record']['opportunity_number'] for r in rows} == {'PA-25-301', 'PA-25-302'}


def test_reporter_single_identifier_overflow_fails_without_truncation(tmp_path):
    client = public_client(tmp_path, lambda request: httpx.Response(
        200, json={'meta': {'total': 15000}, 'results': []}))
    with pytest.raises(SourceError, match='cap'):
        Reporter(client).awards(['PA-25-301'], [2026])


def test_openalex_repeated_cursor_fails(tmp_path):
    client = public_client(tmp_path, lambda request: httpx.Response(200, json={
        'meta': {'count': 1, 'next_cursor': '*'},
        'results': [{'id': 'https://openalex.org/W1',
                     'ids': {'pmid': 'https://pubmed.ncbi.nlm.nih.gov/1'}}],
    }))
    with pytest.raises(SourceError, match='cursor'):
        OpenAlex(client).papers(['1'])


def test_openalex_missing_page_fails(tmp_path):
    client = public_client(tmp_path, lambda request: httpx.Response(200, json={
        'meta': {'count': 2, 'next_cursor': None},
        'results': [{'id': 'https://openalex.org/W1',
                     'ids': {'pmid': 'https://pubmed.ncbi.nlm.nih.gov/1'}}],
    }))
    with pytest.raises(SourceError, match='incomplete'):
        OpenAlex(client).papers(['1', '2'])


def test_reporter_rejects_ignored_foa_filter(tmp_path):
    client = public_client(tmp_path, lambda request: httpx.Response(200, json={
        'meta': {'total': 1}, 'results': [dict(award(1), opportunity_number='UNRELATED')],
    }))
    with pytest.raises(SourceError, match='filter'):
        Reporter(client).awards(['PA-25-301'], [2026])


def test_reporter_repeated_page_does_not_count_as_complete(tmp_path):
    def handle(request):
        body = json.loads(request.content)
        return httpx.Response(200, json={
            'meta': {'total': 501, 'offset': body['offset'], 'limit': 500},
            'results': [award(i) for i in range(500)],
        })

    with pytest.raises(SourceError):
        Reporter(public_client(tmp_path, handle)).awards(['PA-25-301'], [2026])


def test_reporter_publications_split_above_ten_thousand_row_cap(tmp_path):
    queried = []

    def handle(request):
        body = json.loads(request.content)
        ids = body['criteria']['core_project_nums']
        queried.append(ids)
        assert body['sort_field'] == 'pmid'
        assert body['sort_order'] == 'asc'
        if len(ids) == 2:
            return httpx.Response(200, json={'meta': {'total': 10001}, 'results': []})
        row = {'coreproject': ids[0], 'pmid': 1001 if ids[0].endswith('1') else 1002, 'applid': 1}
        return httpx.Response(200, json={'meta': {'total': 1}, 'results': [row]})

    rows = Reporter(public_client(tmp_path, handle)).publications(['R01AI000001', 'R01AI000002'])
    assert len(rows) == 2
    assert len(queried) == 3
    assert {r['record']['coreproject'] for r in rows} == {'R01AI000001', 'R01AI000002'}


def test_reporter_publications_preserve_stable_pmid_sort_across_pages(tmp_path):
    sorts = []

    def handle(request):
        body = json.loads(request.content)
        sorts.append((body.get('sort_field'), body.get('sort_order')))
        start = body['offset']
        return httpx.Response(200, json={
            'meta': {'total': 501, 'offset': start},
            'results': [{'coreproject': 'R01AI000001', 'pmid': 1000 + i, 'applid': 1}
                        for i in range(start, min(start + 500, 501))],
        })

    rows = Reporter(public_client(tmp_path, handle)).publications(['R01AI000001'])
    assert len(rows) == 501
    assert sorts == [('pmid', 'asc'), ('pmid', 'asc')]


def funding_paper(i, core='R01AI145687'):
    return {'id': f'https://openalex.org/W{i}',
            'ids': {'pmid': f'https://pubmed.ncbi.nlm.nih.gov/{i}'},
            'awards': [{'funder_award_id': core}]}


def test_openalex_funding_metadata_pages_are_complete_and_exact(tmp_path):
    pages = []

    def handle(request):
        assert request.url.params['filter'] == 'awards.funder_award_id:R01AI145687'
        assert request.url.params['per-page'] == '200'
        assert 'awards' in request.url.params['select']
        assert 'cursor' not in request.url.params
        page = int(request.url.params['page'])
        pages.append(page)
        start = (page - 1) * 200
        return httpx.Response(200, json={
            'meta': {'count': 201},
            'results': [funding_paper(i) for i in range(start, min(start + 200, 201))],
        })

    rows = OpenAlex(public_client(tmp_path, handle)).papers_for_awards(['R01AI145687'])
    assert len(rows) == 201
    assert pages == [1, 2]
    assert len(list(tmp_path.rglob('*.json'))) == 2


def test_openalex_funding_metadata_mismatch_is_not_a_link(tmp_path):
    client = public_client(tmp_path, lambda request: httpx.Response(200, json={
        'meta': {'count': 1, 'next_cursor': None},
        'results': [funding_paper(1, core='UNRELATED')],
    }))
    with pytest.raises(SourceError, match='exact funding metadata'):
        OpenAlex(client).papers_for_awards(['R01AI145687'])


def test_openalex_funding_metadata_missing_page_fails(tmp_path):
    def handle(request):
        page = int(request.url.params['page'])
        return httpx.Response(200, json={
            'meta': {'count': 201},
            'results': [funding_paper(i) for i in range(200)] if page == 1 else [],
        })

    with pytest.raises(SourceError, match='incomplete|empty'):
        OpenAlex(public_client(tmp_path, handle)).papers_for_awards(['R01AI145687'])


def test_openalex_funding_metadata_overlapping_page_fails(tmp_path):
    client = public_client(tmp_path, lambda request: httpx.Response(200, json={
        'meta': {'count': 201}, 'results': [funding_paper(i) for i in range(200)],
    }))
    with pytest.raises(SourceError, match='overlapping'):
        OpenAlex(client).papers_for_awards(['R01AI145687'])


def test_openalex_funding_metadata_splits_before_public_paging_cap(tmp_path):
    calls = []

    def handle(request):
        ids = request.url.params['filter'].split(':', 1)[1].split('|')
        page = int(request.url.params['page'])
        calls.append((len(ids), page))
        assert page <= 50
        if len(ids) == 2:
            return httpx.Response(200, json={'meta': {'count': 10001}, 'results': []})
        core = ids[0]
        # The two award groups share a single paper, which must be deduplicated.
        indices = list(range(5001)) if core == 'R01AI000001' else list(range(5000, 10001))
        selected = indices[(page - 1) * 200:page * 200]
        rows = []
        for i in selected:
            row = funding_paper(i, core=core)
            if i == 5000:
                row['awards'] = [{'funder_award_id': 'R01AI000001'},
                                 {'funder_award_id': 'R01AI000002'}]
            rows.append(row)
        return httpx.Response(200, json={'meta': {'count': 5001}, 'results': rows})

    rows = OpenAlex(public_client(tmp_path, handle)).papers_for_awards(['R01AI000001', 'R01AI000002'])
    assert len(rows) == 10001
    assert calls[0] == (2, 1)
    assert all(size == 1 for size, _ in calls[1:])


def test_openalex_funding_metadata_total_overshoot_is_rejected(tmp_path):
    client = public_client(tmp_path, lambda request: httpx.Response(200, json={
        'meta': {'count': 1}, 'results': [funding_paper(1), funding_paper(2)],
    }))
    with pytest.raises(SourceError, match='exceeded'):
        OpenAlex(client).papers_for_awards(['R01AI145687'])
