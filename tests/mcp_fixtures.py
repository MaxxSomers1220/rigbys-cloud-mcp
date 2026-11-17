"""Synthetic, deterministic feed fixtures for local Phase 2 checks only.

These records are deliberately marked synthetic; they are not live opportunities
or sale evidence. No key, license or database URL is stored here.
"""
from copy import deepcopy
from datetime import date
import hashlib

from rigbys_feed.database import publish_feed
from rigbys_feed.scoring import METHODOLOGY_VERSION

AS_OF = date(2026, 11, 17)
GENERATED_AT = '2026-11-17T05:00:00+00:00'
NIH = 'National Institutes of Health'
NSF = 'U.S. National Science Foundation'


def _award(identifier, fiscal_year):
    return {'link_type':'award','target_id':identifier,
            'target_url':f'https://reporter.nih.gov/project-details/fixture-{identifier}',
            'join_confidence':1.0,'relationship':'award_reported_under_exact_opportunity_number',
            'fiscal_year':fiscal_year,'award_amount':100000,
            'title':f'Synthetic award {identifier}',
            'evidence':{'fixture':True,'core_project_num':f'TEST-{identifier}',
                        'source_refs':[{'source':'nih_reporter','source_id':identifier,
                                        'fetched_at':GENERATED_AT}]}}


def _paper(identifier, year, via_award):
    return {'link_type':'paper','target_id':f'https://openalex.org/WTEST{identifier}',
            'target_url':f'https://openalex.org/WTEST{identifier}',
            'join_confidence':0.95,'relationship':'publication_associated_with_award_core_project',
            'publication_year':year,'title':f'Synthetic paper {identifier}',
            'evidence':{'fixture':True,'via_award':via_award,
                        'pmid':f'TEST{identifier}', 'application_id_matches':True,
                        'source_refs':[{'source':'openalex','source_id':f'WTEST{identifier}',
                                        'fetched_at':GENERATED_AT}]}}


# Eight topic groups exercise top-five rankings, thin-score exclusion, duplicate
# research IDs and year-window boundaries. A ninth unrelated record tests search.
_CASES = [
    ('cellular mechanisms', '2026-12-01', NIH, (10,20,30,90),
     [('A1',2026),('A2',2025)], [('P1',2026,'A1'),('P2',2025,'A1')]),
    ('gene therapy', '2026-12-20', NIH, (20,30,40,80),
     [('A1',2026),('A3',2027)], [('P2',2025,'A1'),('P3',2026,'A3')]),
    ('diagnostic methods', '2027-01-15', NIH, (30,40,50,70),
     [('A4',2026)], [('P4',2026,'A4'),('P5',2024,'A4')]),
    ('natural history', '2026-11-30', NIH, (40,50,60,60),
     [('A5',2026),('A6',2024)], [('P6',2025,'A5'),('P7',2023,'A6')]),
    ('clinical biomarkers', '2026-12-10', NIH, (50,60,70,40),
     [('A7',2027),('A8',2026)], [('P8',2026,'A8')]),
    ('population research', None, NIH, (60,70,80,20),
     [('A8',2026),('A9',2023)], [('P8',2026,'A8'),('P9',2027,'A8')]),
    ('computational methods', '2027-01-02', NIH, None, [], []),
    ('data infrastructure', '2026-12-05', NSF, None, [], []),
]


def fixture_records():
    """Return a new mutable nine-record fixture with complete Phase 1 fields."""
    records = []
    for index, (topic, deadline, sponsor, scores, awards, papers) in enumerate(_CASES,1):
        title = 'Rare disease '+topic
        refs = {field:[{'source':'grants_gov','source_id':f'fixture-{index}',
                        'url':f'https://www.grants.gov/search-results-detail/fixture-{index}',
                        'field':field,'fetched_at':GENERATED_AT}]
                for field in ('title_normalized','sponsor_normalized','deadline_parsed',
                              'award_amount_parsed','eligibility_parsed','summary_short')}
        linked_awards = [_award(*a) for a in awards]
        linked_papers = [_paper(*p) for p in papers]
        opportunity_id = f'fixture-{index:04d}'
        for linked in linked_awards+linked_papers:
            linked['opportunity_id']=opportunity_id
        score_values = scores if scores is not None else (50,50,50,50)
        record = {
            'opportunity_id':opportunity_id,
            'dedupe_key':hashlib.sha256(opportunity_id.encode()).hexdigest(),
            'opportunity_number':f'TEST-26-{index:03d}',
            'title_normalized':title,'sponsor_normalized':sponsor,
            'deadline_parsed':deadline+'T00:00:00+00:00' if deadline else None,
            'deadline_precision':'date' if deadline else 'rolling',
            'source_deadline_date':deadline+'T00:00:00+00:00' if deadline else None,
            'deadline_description':'' if deadline else 'Applications accepted on a rolling basis.',
            'eligibility_parsed':['Public and State controlled institutions of higher education'],
            'award_amount_parsed':{'currency':'USD','floor':0,'ceiling':100000},
            'source_ids':[{'source':'grants_gov','id':f'fixture-{index}'}],
            'description':f'Synthetic public research support for rare disease {topic}.',
            'summary_short':f'Synthetic rare disease {topic} opportunity; verify source requirements.',
            'extracted_requirements':['Synthetic fixture eligibility requirement'],
            'linked_awards':linked_awards,'linked_papers':linked_papers,
            'links':[deepcopy(edge) for edge in linked_awards+linked_papers],
            'join_status':'exact_identifier_links' if awards else 'no_confirmed_award_in_scoped_sources',
            'research_coverage':{'fixture':True,'fiscal_years':[2024,2025,2026,2027]},
            'methodology_version':METHODOLOGY_VERSION,
            'score_evidence':{'status':'descriptive_proxy' if scores is not None
                              else 'insufficient_data_neutral_placeholder',
                              'inputs':{'fixture':True,'award_count':len(awards),'paper_count':len(papers)}},
            'feed_generated_at':GENERATED_AT,'fetched_at':GENERATED_AT,'updated_at':GENERATED_AT,
            'source_refs':refs,'change_log':[], 'quality_flags':['synthetic_test_fixture']}
        record.update(dict(zip(('growth_score','momentum_score','novelty_score','gap_score'),score_values)))
        records.append(record)
    unrelated=deepcopy(records[0])
    unrelated['opportunity_id']='fixture-0009'
    unrelated['dedupe_key']=hashlib.sha256(b'fixture-0009').hexdigest()
    unrelated['opportunity_number']='TEST-26-009'
    unrelated['title_normalized']='Renewable energy grid reliability'
    unrelated['description']='Synthetic energy research opportunity.'
    unrelated['summary_short']='Synthetic renewable energy infrastructure support.'
    unrelated['linked_awards']=[];unrelated['linked_papers']=[];unrelated['links']=[]
    unrelated['join_status']='no_confirmed_award_in_scoped_sources'
    unrelated['score_evidence']={'status':'insufficient_data_neutral_placeholder',
                                 'inputs':{'fixture':True,'award_count':0,'paper_count':0}}
    for field in ('growth_score','momentum_score','novelty_score','gap_score'):
        unrelated[field]=50
    unrelated['source_ids']=[{'source':'grants_gov','id':'fixture-9'}]
    for refs in unrelated['source_refs'].values():
        for ref in refs:
            ref['source_id']='fixture-9'
            ref['url']='https://www.grants.gov/search-results-detail/fixture-9'
    records.append(unrelated)
    return records


EXPECTED_RARE_DISEASE = {
    'topic':'rare disease','as_of':'2026-11-17','window_months':12,
    'open_opportunity_count':8,'awarded_grant_count':6,'paper_count':6,
    'insufficient_data_count':2,'scored_opportunity_count':6,
    'eligible_award_ids':['A1','A3','A4','A5','A7','A8'],
    'eligible_paper_ids':['https://openalex.org/WTESTP1','https://openalex.org/WTESTP2',
                          'https://openalex.org/WTESTP3','https://openalex.org/WTESTP4',
                          'https://openalex.org/WTESTP6','https://openalex.org/WTESTP8'],
    'median_growth_score':35,'median_momentum_score':45,
    'median_novelty_score':55,'median_gap_score':65,
    'neglected_titles':['Rare disease '+topic for topic in
                        ('cellular mechanisms','gene therapy','diagnostic methods',
                         'natural history','clinical biomarkers')],
    'crowded_titles':['Rare disease '+topic for topic in
                      ('population research','clinical biomarkers','natural history',
                       'diagnostic methods','gene therapy')],
    'source_counts':{'grants_gov':8,'nih_reporter':6,'openalex':6},
    'nih_sponsor_match_count':7,
    'note':'Counts use fiscal-year/calendar-year intervals overlapping 2025-11-17 through 2026-11-17.'}


def seed_feed(conn, generated_at=GENERATED_AT):
    """Publish only synthetic test data into the caller's isolated test database."""
    records=fixture_records()
    publish_feed(conn,records,generated_at,{'grants_gov':9,'nih_reporter_awards':9,'openalex':9},
                 {'grants_gov':{'status':'fixture','last_success_at':generated_at},
                  'nih_reporter':{'status':'fixture','last_success_at':generated_at},
                  'openalex':{'status':'fixture','last_success_at':generated_at}})
    return records
