"""Verified same-program award evidence from the public NSF Award Search."""
from concurrent.futures import ThreadPoolExecutor
import re
from urllib.parse import urlencode

from .sources import SourceError

SOURCE = 'nsf_award_search'
SPONSOR = 'U.S. National Science Foundation'
PROGRAM_BASE = 'https://www.nsf.gov/funding/opportunities/'
AWARD_BASE = 'https://www.nsf.gov/awardsearch/'

# Each solicitation redirects from its Grants.gov funding link to a page on
# the listed NSF program. Codes are those advertised in that program page's
# "Awards made through this program" section. See the linkage evidence.
PROGRAMS = {
    '22-621': ('aapf-nsf-astronomy-astrophysics-postdoctoral-fellowships', '160900'),
    '23-525': ('oceanographic-facilities-equipment-support', '541100,541200,541300,541500,541600,541700'),
    '23-580': ('capacity-infrastructure-capacity-biological-research', '167Y00,168Y00,169Y00'),
    '23-598': ('hbcu-eir-historically-black-colleges-universities-excellence-research', '070Y00'),
    '24-503': ('research-experiences-teachers-engineering-computer-science', '135900'),
    '24-564': ('iusepfe-red-iuseprofessional-formation-engineers-revolutionizing', '012Y00'),
    '24-584': ('ate-advanced-technological-education', '741200'),
    '25-522': ('e-rise-epscor-research-infrastructure-improvement-program-epscor', '269Y00'),
    '25-523': ('e-core-epscor-research-infrastructure-improvement-program-epscor', '270Y00'),
    '25-531': ('cici-cybersecurity-innovation-cyberinfrastructure', '802700'),
    'PD-20-1260': ('mathinf-mathematical-sciences-infrastructure-program', '126000'),
}


def opportunity_numbers(grants):
    numbers = set()
    for grant in grants:
        raw = grant['record']
        agency = raw.get('agencyDetails') or raw['synopsis'].get('agencyDetails') or {}
        if agency.get('topAgencyCode') == 'NSF' or raw.get('owningAgencyCode') == 'NSF':
            number = raw['opportunityNumber'].strip().upper()
            if number in PROGRAMS:
                numbers.add(number)
    return numbers


def program_evidence(number):
    slug, codes = PROGRAMS[number]
    program = PROGRAM_BASE + slug
    params = {'ProgEleCode': codes, 'BooleanElement': 'Any',
              'BooleanRef': 'Any', 'ActiveAwards': 'true'}
    return {
        'opportunity_number': number,
        'nsf_solicitation_url': program if number.startswith('PD-') else program + f'/nsf{number}/solicitation',
        'nsf_program_url': program,
        'nsf_program_award_search_url': AWARD_BASE + 'search-results/?' + urlencode(params),
    }


class NsfAwardSearch:
    url = 'https://api.nsf.gov/services/v1/awards.json'

    def __init__(self, http):
        self.http = http

    def _program_awards(self, number):
        codes = PROGRAMS[number][1]
        expected_codes = set(codes.split(','))
        awards, seen = [], set()
        offset, total, oldest = 0, None, None
        while True:
            data, ref = self.http.request(SOURCE, 'GET', self.url, params={
                'ProgEleCode': codes, 'BooleanElement': 'Any', 'ActiveAwards': 'true',
                'rpp': 100, 'offset': offset,
            })
            response = data.get('response', {})
            rows, meta = response.get('award'), response.get('metadata', {})
            count = meta.get('totalCount')
            if (not isinstance(rows, list) or type(count) is not int
                    or not 0 <= count < 10000 or meta.get('offset') != offset
                    or (total is not None and total != count)):
                raise SourceError(f'{SOURCE}: invalid or capped program award page')
            total = count
            oldest = min(oldest, ref['fetched_at']) if oldest else ref['fetched_at']
            for row in rows:
                award_id = row.get('id', '')
                if not re.fullmatch(r'[0-9]+', award_id) or award_id in seen:
                    raise SourceError(f'{SOURCE}: invalid or repeated award ID')
                seen.add(award_id)
                row_codes = {code.strip().upper() for code in (row.get('progEleCode') or '').split(',')}
                matched = sorted(row_codes & expected_codes)
                # The public search can consider secondary codes. Require a
                # code the individual award response actually exposes.
                if matched and row.get('agency') == 'NSF' and row.get('activeAwd') == 'true':
                    awards.append({'id': award_id, 'title': row.get('title'),
                                   'source_award_date': row.get('initAmendmentDate'),
                                   'matched_program_codes': matched, 'ref': ref})
            offset += len(rows)
            if offset == total:
                return number, {'awards': awards, 'fetched_at': oldest, 'source_results': total}
            if not rows or offset > total:
                raise SourceError(f'{SOURCE}: incomplete program award pages')

    def awards(self, numbers):
        with ThreadPoolExecutor(max_workers=3) as pool:
            return dict(pool.map(self._program_awards, sorted(numbers)))


def attach_nsf_awards(records, programs):
    for record in records:
        number = record['opportunity_number']
        evidence = []
        if record['sponsor_normalized'] == SPONSOR and number in programs:
            refs = program_evidence(number)
            for award in programs[number]['awards']:
                award_id = award['id']
                evidence.append({
                    'opportunity_id': record['opportunity_id'], 'link_type': 'award',
                    'target_id': award_id, 'target_url': AWARD_BASE + 'show-award/?AWD_ID=' + award_id,
                    'title': award['title'], 'source_award_date': award['source_award_date'],
                    'join_confidence': 0.95, 'relationship': 'nsf_award_in_same_verified_program',
                    'evidence': {**refs, 'matched_program_codes': award['matched_program_codes'],
                                 'award_ref': award['ref']},
                })
        record['linked_nsf_program_awards'] = sorted(evidence, key=lambda award: award['target_id'])
        record['source_refs']['linked_nsf_program_awards'] = [{
            'source': SOURCE, 'evidence_field': 'linked_nsf_program_awards[].evidence',
            'note': 'Same-program award evidence is stored separately from exact-solicitation score inputs.'}]
        record['source_ids'].extend({'source': SOURCE, 'id': award['target_id']}
                                    for award in record['linked_nsf_program_awards'])
