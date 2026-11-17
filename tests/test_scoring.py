from copy import deepcopy
from datetime import date
from rigbys_feed.scoring import score


def fixture(awards=200,papers=1000):
    return {'source_refs':{},'linked_awards':[{'fiscal_year':2026 if i%2 else 2025} for i in range(awards)],
            'linked_papers':[{'publication_year':2025 if i%2 else 2024} for i in range(papers)]}


def test_corn_in_a_rut_and_determinism():
    original=fixture()
    a=score(deepcopy(original),date(2026,11,17))
    b=score(deepcopy(original),date(2026,11,17))
    assert a==b
    assert a['novelty_score']<10
    assert a['momentum_score']==0
    assert a['growth_score']==0
    assert a['methodology_version']=='research-signals-1.0.0'
    for f in ('growth_score','momentum_score','novelty_score','gap_score'):
        assert 0<=a[f]<=100
        assert a['source_refs'][f]


def test_thin_is_neutral_not_neglected():
    a=score(fixture(0,0),date(2026,11,17))
    assert all(a[f]==50 for f in ('growth_score','momentum_score','novelty_score','gap_score'))
    assert a['score_evidence']['status']=='insufficient_data_neutral_placeholder'


def test_current_incomplete_year_not_compared():
    a=fixture(20,20)
    a['linked_papers'] += [{'publication_year':2026}]*500
    a['linked_awards'] += [{'fiscal_year':2027}]*500
    s=score(a,date(2026,11,17))
    assert s['growth_score']==s['momentum_score']==0
