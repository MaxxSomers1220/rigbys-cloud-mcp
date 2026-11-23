from datetime import date

import pytest

from rigbys_feed.clinical_trials import ClinicalTrials, attach_trials
from rigbys_feed.nsf import NsfAwardSearch, attach_nsf_awards
from rigbys_feed.scoring import score
from rigbys_feed.sources import SourceError


class Responses:
    def __init__(self, pages):
        self.pages = iter(pages)
        self.params = []

    def request(self, source, method, url, *, params):
        assert method == 'GET'
        self.params.append(params)
        return next(self.pages), {'source': source, 'url': url,
                                  'fetched_at': '2026-11-21T06:00:00+00:00'}


def study(nct, identifiers):
    return {'protocolSection': {'identificationModule': {
        'nctId': nct, 'briefTitle': 'Study fixture', 'secondaryIdInfos': identifiers}}}


def test_trial_paging_and_exact_evidence():
    nih_id = {'id': '1 R01 AI123456-02A1', 'type': 'NIH'}
    item1 = study('NCT01234567', [nih_id, {'id': 'R01AI123457', 'type': 'OTHER_GRANT'}])
    item2 = study('NCT01234568', [nih_id])
    http = Responses([{'studies': [item1], 'totalCount': 2, 'nextPageToken': 'second'},
                      {'studies': [item2]}])
    studies, _ = ClinicalTrials(http).nih_studies()
    assert http.params[1]['pageToken'] == 'second'
    assert studies['NCT01234567']['nih_ids'] == {'1 R01 AI123456-02A1': 'R01AI123456'}
    award = {'evidence': {'core_project_num': 'R01AI123456'}, 'target_id': '1R01AI123456-01',
             'target_url': 'https://reporter.nih.gov/project-details/1'}
    record = {'opportunity_id': 'gg-1', 'title_normalized': 'See NCT01234567',
              'description': 'Another known ID: XNCT01234569. Similar subject.',
              'source_refs': {'title_normalized': [{'url': 'https://www.grants.gov/search-results-detail/1'}]},
              'source_ids': [], 'linked_awards': [award]}
    attach_trials([record], studies)
    direct, via_award = record['linked_trials']
    assert direct['relationship'] == 'study_id_cited_in_opportunity'
    assert direct['join_confidence'] == 1.0
    assert via_award['target_id'] == 'NCT01234568'
    assert via_award['relationship'] == 'study_registry_reports_linked_nih_award'
    assert via_award['evidence']['registry_nih_id'] == nih_id['id']


def test_incomplete_trial_pagination_is_rejected():
    http = Responses([{'studies': [study('NCT01234567', [])], 'totalCount': 2}])
    with pytest.raises(SourceError, match='incomplete'):
        ClinicalTrials(http).nih_studies()


def test_nsf_context_requires_verified_code_and_sponsor():
    def award(award_id, code):
        return {'id': award_id, 'title': 'Award fixture', 'agency': 'NSF',
                'activeAwd': 'true', 'progEleCode': code, 'initAmendmentDate': '01/01/2026'}
    first = {'award': [award('1234567', '802700')], 'metadata': {'offset': 0, 'totalCount': 2}}
    next_page = {'award': [award('1234568', '999999')], 'metadata': {'offset': 1, 'totalCount': 2}}
    http = Responses([{'response': first}, {'response': next_page}])
    programs = NsfAwardSearch(http).awards({'25-531'})
    assert http.params[0]['ProgEleCode'] == '802700'
    assert http.params[1]['offset'] == 1
    assert all(page['rpp'] == 25 and page['sortKey'] == 'awardNumber' for page in http.params)
    fake_sponsor, actual = [
        {'opportunity_id': uid, 'opportunity_number': '25-531', 'sponsor_normalized': sponsor,
         'source_refs': {}, 'source_ids': [], 'linked_awards': [], 'linked_papers': []}
        for uid, sponsor in [('gg-1', 'A different agency'), ('gg-2', 'U.S. National Science Foundation')]]
    attach_nsf_awards([fake_sponsor, actual], programs)
    assert fake_sponsor['linked_nsf_program_awards'] == []
    edge, = actual['linked_nsf_program_awards']
    assert edge['target_id'] == '1234567'
    assert edge['relationship'] == 'nsf_award_in_same_verified_program'
    assert edge['evidence']['matched_program_codes'] == ['802700']
    score(actual, date(2026, 11, 21))
    assert actual['score_evidence']['inputs']['award_count'] == 0
    assert actual['score_evidence_detail']['basis'] == 'neutral_placeholder'


def test_nsf_repeated_award_across_pages_is_rejected():
    repeated = {'id': '1234567'}
    pages = [
        {'response': {'award': [repeated], 'metadata': {'offset': offset, 'totalCount': 2}}}
        for offset in (0, 1)
    ]
    with pytest.raises(SourceError, match='repeated award ID'):
        NsfAwardSearch(Responses(pages)).awards({'25-531'})


def test_score_inputs_point_to_the_contributing_links():
    papers = [{'publication_year': year, 'target_id': f'paper-{idx}',
               'target_url': f'https://openalex.org/W{idx}', 'join_confidence': 0.95}
              for idx, year in enumerate([2025] * 4 + [2024] * 3 + [2023] * 3)]
    awards = [{'fiscal_year': year, 'target_id': f'award-{idx}',
               'target_url': f'https://reporter.nih.gov/project-details/{idx}', 'join_confidence': 1.0}
              for idx, year in enumerate([2026] * 3 + [2025] * 2)]
    record = {'linked_awards': awards, 'linked_papers': papers, 'source_refs': {}}
    score(record, date(2026, 11, 21))
    detail = record['score_evidence_detail']
    assert detail['basis'] == 'linked_research'
    assert detail['scores']['growth_score']['inputs'] == ['paper_recent', 'paper_previous']
    assert [p['target_id'] for p in papers if 'paper_recent' in p['score_inputs']] == [
        'paper-0', 'paper-1', 'paper-2', 'paper-3']
    assert [a['target_id'] for a in awards if 'award_previous' in a['score_inputs']] == [
        'award-3', 'award-4']
    assert sum('paper_count' in p['score_inputs'] for p in papers) == 10
    assert all(link['target_url'] and 0 <= link['join_confidence'] <= 1 for link in papers + awards)
