from copy import deepcopy
from datetime import date
import pytest

from mcp_fixtures import fixture_records,EXPECTED_RARE_DISEASE
from rigbys_mcp.aggregation import aggregate


def matched():
    return fixture_records()[:8]


def test_gap_matches_hand_calculated_distinct_counts_and_medians():
    result=aggregate(matched(),'rare disease',12,date(2026,11,17))
    expected=EXPECTED_RARE_DISEASE
    for field in ('open_opportunity_count','awarded_grant_count','paper_count',
                  'insufficient_data_count','scored_opportunity_count','median_growth_score',
                  'median_momentum_score','median_novelty_score','median_gap_score','source_counts'):
        assert result[field]==expected[field]
    assert [g['subtopic'] for g in result['top_neglected_subtopics']]==expected['neglected_titles']
    assert [g['subtopic'] for g in result['top_crowded_subtopics']]==expected['crowded_titles']
    assert result['grouping_method']=='normalized opportunity-title groups; not scientific taxonomy'
    assert result['window_start']=='2025-11-17'
    assert result['sample_status']=='thin_sample'
    assert result['neutral_placeholder_count']==2
    assert result['neutral_placeholder_value']==50
    assert result['methodology_version']=='research-signals-1.0.0'
    for group in result['top_neglected_subtopics']+result['top_crowded_subtopics']:
        assert group['source_counts']['grants_gov']==1
        assert group['source_refs'][0]['opportunity_id'] in group['opportunity_ids']
        assert group['source_refs'][0]['source_url'].startswith('https://www.grants.gov/')
        assert group['methodology_version']==result['methodology_version']


def test_year_window_counts_previous_calendar_year_and_current_fiscal_year():
    rows=matched()
    result=aggregate(rows,'rare disease',12,'2026-11-17')
    # FY2025 has ended before cutoff. FY2027 overlaps current October onward.
    assert result['awarded_grant_count']==6
    # Publication2025 overlaps cutoff; future2027 and old2024 do not.
    assert result['paper_count']==6
    assert 'not exact award/publication dates' in result['window_precision']
    expanded=aggregate(rows,'rare disease',36,'2026-11-17')
    assert expanded['awarded_grant_count']==8
    assert expanded['paper_count']==8


def test_no_counts_or_comparisons_invented_for_empty_and_thin():
    empty=aggregate([],'unknown',as_of='2026-11-17')
    assert empty['open_opportunity_count']==empty['awarded_grant_count']==empty['paper_count']==0
    assert empty['median_gap_score'] is None
    assert empty['top_neglected_subtopics']==empty['top_crowded_subtopics']==[]
    assert empty['methodology_version'] is None
    assert empty['sample_status']=='no_matching_opportunities'
    thin=aggregate(matched()[-2:],'rare disease',as_of='2026-11-17')
    assert thin['open_opportunity_count']==2
    assert thin['insufficient_data_count']==thin['neutral_placeholder_count']==2
    assert thin['median_gap_score'] is None
    assert thin['top_neglected_subtopics']==thin['top_crowded_subtopics']==[]
    assert thin['sample_status']=='insufficient_data'


def test_mixed_and_missing_methodologies_suppress_ranking_without_fabricated_version():
    rows=matched()
    rows[0]['methodology_version']='research-signals-2.0.0'
    mixed=aggregate(rows,'rare disease',as_of='2026-11-17')
    assert mixed['methodology_version'] is None
    assert mixed['methodology_versions']==['research-signals-1.0.0','research-signals-2.0.0']
    assert mixed['median_growth_score']==mixed['median_gap_score'] is None
    assert mixed['top_neglected_subtopics']==mixed['top_crowded_subtopics']==[]
    assert mixed['sample_status']=='mixed_methodologies'
    rows=matched();rows[0]['methodology_version']=None
    missing=aggregate(rows,'rare disease',as_of='2026-11-17')
    assert missing['median_gap_score'] is None
    assert missing['sample_status']=='methodology_unavailable'


@pytest.mark.parametrize('window',[0,121,-1,True,False,1.5,'12',None])
def test_invalid_window_rejected(window):
    with pytest.raises(ValueError,match='1 to 120'):
        aggregate(matched(),'rare disease',window,'2026-11-17')


def test_window_caps_and_calendar_month_boundary():
    assert aggregate(matched(),'rare disease',1,'2026-03-31')['window_start']=='2026-02-28'
    assert aggregate(matched(),'rare disease',120,'2026-11-17')['window_start']=='2016-11-17'
    assert aggregate(matched(),'rare disease',12,'2024-02-29')['window_start']=='2023-02-28'


def test_ties_are_alphabetical_and_duplicate_ids_not_double_counted():
    rows=matched()
    for row in rows[:6]: row['gap_score']=60
    output=aggregate(list(reversed(rows))+[deepcopy(rows[0])],'rare disease',as_of='2026-11-17')
    assert output['open_opportunity_count']==8
    titles=sorted([r['title_normalized'] for r in rows[:6]],key=str.casefold)[:5]
    assert [g['subtopic'] for g in output['top_neglected_subtopics']]==titles
    assert [g['subtopic'] for g in output['top_crowded_subtopics']]==titles
    assert output['awarded_grant_count']==output['paper_count']==6


def test_unknown_periods_are_disclosed_without_fake_dates_or_counts():
    rows=matched()[:1]
    rows[0]['linked_awards'][0]['fiscal_year']=None
    rows[0]['linked_papers'][0]['publication_year']=None
    result=aggregate(rows,'rare disease',as_of='2026-11-17')
    assert result['award_period_unknown_count']==1
    assert result['paper_period_unknown_count']==1
    assert result['awarded_grant_count']==0
    assert result['paper_count']==1


def test_postgres_wrapper_matches_hand_computed_fixture(database,monkeypatch):
    from rigbys_mcp.repository import Repository
    from rigbys_mcp import aggregation
    from mcp_fixtures import seed_feed,EXPECTED_RARE_DISEASE,AS_OF
    monkeypatch.setenv('DATABASE_URL',database.info.dsn);seed_feed(database)
    original=aggregation._as_date
    monkeypatch.setattr(aggregation,'_as_date',lambda value:AS_OF if value is None else original(value))
    result=Repository().gap('rare disease')
    for field in ('open_opportunity_count','awarded_grant_count','paper_count','source_counts',
                  'median_growth_score','median_momentum_score','median_novelty_score','median_gap_score'):
        assert result[field]==EXPECTED_RARE_DISEASE[field]
    assert [x['subtopic'] for x in result['top_neglected_subtopics']]==EXPECTED_RARE_DISEASE['neglected_titles']
    assert [x['subtopic'] for x in result['top_crowded_subtopics']]==EXPECTED_RARE_DISEASE['crowded_titles']

from test_database import database


def test_postgres_gap_projection_matches_same_hand_aggregation(database,monkeypatch):
    from mcp_fixtures import seed_feed,AS_OF
    from rigbys_mcp import aggregation
    from rigbys_mcp.repository import Repository,QueryError
    original=aggregation._as_date
    monkeypatch.setattr(aggregation,'_as_date',lambda value:AS_OF if value is None else original(value))
    monkeypatch.setenv('DATABASE_URL',database.info.dsn)
    seed_feed(database)
    result=Repository().gap('rare disease')
    for field in ('open_opportunity_count','awarded_grant_count','paper_count',
                  'median_growth_score','median_momentum_score','median_novelty_score','median_gap_score'):
        assert result[field]==EXPECTED_RARE_DISEASE[field]
    assert result['source_counts']==EXPECTED_RARE_DISEASE['source_counts']
    assert result['feed_generated_at'].startswith('2026-11-17T05:00:00')
    assert Repository().gap('solar nonexistent')['open_opportunity_count']==0
    with pytest.raises(QueryError):
        Repository().gap('rare disease',121)
    assert database.execute('SELECT count(*) FROM opportunities').fetchone()[0]==9


from test_database import database
