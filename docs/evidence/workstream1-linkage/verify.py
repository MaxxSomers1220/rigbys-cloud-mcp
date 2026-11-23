"""Replay a dated export against public records, without writing to production."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import gzip
from html import unescape
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen

from rigbys_feed.builder import ResumeClient
from rigbys_feed.clinical_trials import ClinicalTrials, attach_trials, nih_core
from rigbys_feed.nsf import PROGRAMS, SPONSOR, NsfAwardSearch, attach_nsf_awards
from rigbys_feed.scoring import score
from rigbys_feed.sources import GrantsGov


SCORES = ('growth_score', 'momentum_score', 'novelty_score', 'gap_score')


def get_html(url):
    with urlopen(url, timeout=45) as response:
        return response.geturl(), response.read().decode('utf-8')


def verify_program_award(http, record):
    opportunity_id = record['opportunity_id']
    opportunity = GrantsGov(http).detail(opportunity_id.removeprefix('gg-'))['record']
    assert opportunity['opportunityNumber'].strip().upper() == record['opportunity_number']
    assert opportunity['agencyDetails']['topAgencyCode'] == 'NSF'
    edge = record['linked_nsf_program_awards'][0]
    evidence = edge['evidence']
    funding_url = opportunity['synopsis']['fundingDescLinkUrl']
    # The source feed points directly to official NSF solicitations.
    assert urlsplit(funding_url).hostname == 'www.nsf.gov'
    solicitation, _ = get_html(funding_url.replace('http:', 'https:', 1))
    assert solicitation.rstrip('/') == evidence['nsf_solicitation_url'].rstrip('/')
    program_url, program_html = get_html(evidence['nsf_program_url'])
    section = re.search(r'<section class="program__award-url[^"]*"[^>]*>(.*?)</section>',
                        program_html, re.DOTALL)[1]
    assert 'Awards made through this program' in section
    live_search_url = unescape(re.search(r'href="([^"]+)"', section)[1])
    live_codes = set(parse_qs(urlsplit(live_search_url).query)['ProgEleCode'][0].split(','))
    expected_codes = set(PROGRAMS[record['opportunity_number']][1].split(','))
    assert expected_codes <= live_codes, (record['opportunity_number'], expected_codes, live_codes)
    award_url, _ = get_html(edge['target_url'])
    # The human award page loads its details from the JSON API at runtime.
    data, _ = http.request('nsf_award_search', 'GET', NsfAwardSearch.url,
                           params={'id': edge['target_id']})
    award, = data['response']['award']
    assert award['id'] == edge['target_id']
    assert award['agency'] == 'NSF'
    assert award['title'] == edge['title']
    award_codes = {code.strip() for code in award['progEleCode'].split(',')}
    for code in evidence['matched_program_codes']:
        assert code in live_codes
        assert code in award_codes
    return {'opportunity_id': opportunity_id, 'opportunity_number': record['opportunity_number'],
            'grants_gov': record['source_refs']['title_normalized'][0]['url'],
            'nsf_solicitation': solicitation, 'nsf_program': program_url,
            'nsf_program_awards': live_search_url, 'award_id': edge['target_id'],
            'nsf_award': award_url, 'nsf_award_record': NsfAwardSearch.url + '?id=' + edge['target_id'],
            'verified_codes': evidence['matched_program_codes'],
            'relationship': edge['relationship'], 'join_confidence': edge['join_confidence']}


def verify_trial(http, record):
    edge = record['linked_trials'][0]
    evidence = edge['evidence']
    trial, _ = http.request('clinical_trials_gov', 'GET', ClinicalTrials.url + '/' + edge['target_id'])
    identity = trial['protocolSection']['identificationModule']
    assert identity['nctId'] == edge['target_id']
    assert any(item.get('type') == 'NIH' and item.get('id') == evidence['registry_nih_id']
               and nih_core(item['id']) == evidence['core_project_num']
               for item in identity['secondaryIdInfos'])
    award = next(award for award in record['linked_awards'] if award['target_id'] == evidence['via_award'])
    assert award['evidence']['core_project_num'] == evidence['core_project_num']
    assert award['evidence']['opportunity_number'] == record['opportunity_number']
    assert award['target_url'] == evidence['award_url']
    return {'opportunity_id': record['opportunity_id'], 'opportunity_number': record['opportunity_number'],
            'grants_gov': record['source_refs']['title_normalized'][0]['url'],
            'trial': edge['target_url'], 'reporter_award': evidence['award_url'],
            'registry_reported_award_id': evidence['registry_nih_id'],
            'reporter_award_core': evidence['core_project_num'],
            'join_confidence': edge['join_confidence']}


def audit(export, raw_dir):
    http = ResumeClient(raw_dir)
    with gzip.open(export, 'rt') as file:
        snapshot = json.load(file)
    records = snapshot['opportunities']
    assert len(records) == snapshot['record_count'] == len({r['opportunity_id'] for r in records})
    generation = snapshot['feed_generated_at']
    as_of = date.fromisoformat(generation[:10])
    before = {r['opportunity_id'] for r in records if r['linked_awards'] or r['linked_papers']}
    nsf = [r for r in records if r['sponsor_normalized'] == SPONSOR]
    programs = NsfAwardSearch(http).awards({r['opportunity_number'] for r in nsf} & PROGRAMS.keys())
    trials, stamp = ClinicalTrials(http).nih_studies()
    attach_nsf_awards(records, programs)
    attach_trials(records, trials)
    all_awards = {award['target_id'] for r in records for award in r['linked_nsf_program_awards']}
    trial_rows = [r for r in records if r['linked_trials']]
    augmented = {r['opportunity_id'] for r in records if r['linked_trials'] or r['linked_nsf_program_awards']} | before
    new_rows = sorted((r for r in records if r['opportunity_id'] in augmented - before),
                      key=lambda r: r['opportunity_id'])
    basis = Counter()
    for r in records:
        numeric = tuple(r[k] for k in SCORES)
        score(r, as_of)
        assert tuple(r[k] for k in SCORES) == numeric
        basis[r['score_evidence_detail']['basis']] += 1
        observed = Counter(tag for kind in ('awards', 'papers') for link in r['linked_' + kind]
                           for tag in link['score_inputs'])
        for tag in ('award_count', 'paper_count', 'award_recent', 'award_previous', 'paper_recent', 'paper_previous'):
            assert observed[tag] == r['score_evidence']['inputs'][tag]
    with ThreadPoolExecutor(max_workers=5) as pool:
        new_checks = list(pool.map(lambda row: verify_program_award(http, row), new_rows))
        trial_checks = list(pool.map(lambda row: verify_trial(http, row), trial_rows[:5]))
    assert len(new_checks) >= 10
    return {
        'source_feed_generated_at': generation, 'record_count': len(records),
        'historical_nov19_approximate': {'award_or_paper_linked': 165, 'records': 786},
        'before_award_or_paper_linked': len(before), 'after_award_or_paper_linked': len(before),
        'after_any_confirmed_research_link': len(augmented), 'newly_linked_opportunities': len(new_rows),
        'nsf_opportunities_in_feed': len(nsf),
        'nsf_programs': {n: {'source_rows': p['source_results'], 'confirmed_awards': len(p['awards'])}
                         for n, p in programs.items()},
        'nsf_distinct_program_awards': len(all_awards),
        'nsf_program_award_links': sum(len(r['linked_nsf_program_awards']) for r in records),
        'clinical_trials_first_source_fetch_at': stamp, 'registry_studies_reviewed_by_adapter': len(trials),
        'trial_linked_opportunities': len(trial_rows),
        'trial_links': sum(len(r['linked_trials']) for r in trial_rows),
        'unique_linked_trials': len({edge['target_id'] for r in trial_rows for edge in r['linked_trials']}),
        'same_numeric_score_records': len(records), 'score_basis_counts': dict(basis),
        'new_link_spot_checks': new_checks, 'trial_spot_checks': trial_checks,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('export', type=Path)
    parser.add_argument('raw_dir', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(args.export, args.raw_dir), ensure_ascii=False, indent=2) + '\n')
