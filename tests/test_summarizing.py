from datetime import date
from rigbys_feed.cleaning import clean
from rigbys_feed.summarizing import summarize
from test_cleaning import item


def test_summary_only_source_facts_and_full_restrictions():
    r=summarize(clean(item(),date(2026,11,17)))
    assert '2027-01-02' in r['summary_short']
    assert '$1,200,000.00' in r['summary_short']
    assert 'Foreign entities are not eligible.' in r['extracted_requirements']
    assert r['source_refs']['summary_short']


def test_rolling_summary_never_turns_placeholder_into_deadline():
    raw=item();s=raw['record']['synopsis'];s['responseDateStr']='2076-01-01-00-00-00'
    s['responseDateDesc']='Proposals accepted anytime';s['awardFloor']=s['awardCeiling']='none'
    r=summarize(clean(raw,date(2026,11,17)))
    assert '2076' not in r['summary_short']
    assert 'Rolling submission' in r['summary_short']
    assert 'Award bounds not specified' in r['summary_short']
    assert '$' not in r['summary_short']
