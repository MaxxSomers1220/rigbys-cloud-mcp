from datetime import date
import pytest
from rigbys_feed.cleaning import clean, amount, deadline


def item():
    return {'ref': {'fetched_at': '2026-11-17T00:00:00Z'}, 'record': {
        'id': 123, 'opportunityNumber': ' PA-26-001 ', 'opportunityTitle': '<b>Public   health</b>',
        'agencyDetails': {'agencyCode':'HHS-NIH11','agencyName':'National Institutes of Health'},
        'synopsis': {'agencyName':'Contact Person', 'responseDateStr':'2027-01-02-00-00-00',
        'awardFloor':'0','awardCeiling':'$1,200,000','applicantTypes':[{'description':'Small businesses'}],
        'applicantEligibilityDesc':'Foreign entities are not eligible.'}}}


def test_structured_cleaning_and_restrictions():
    r=clean(item(),date(2026,11,17))
    assert r['title_normalized']=='Public health'
    assert r['sponsor_normalized']=='National Institutes of Health'
    assert r['deadline_parsed'][:10]=='2027-01-02'
    assert r['award_amount_parsed']['ceiling']==1200000
    assert 'Foreign entities are not eligible.' in r['eligibility_parsed']
    assert r['award_amount_parsed']['floor']==0


def test_expired_and_unknown_and_invalid():
    raw=item();raw['record']['synopsis']['responseDateStr']='2020-01-01-00-00-00'
    assert clean(raw,date(2026,11,17)) is None
    assert deadline({}) is None
    assert amount('none') is None
    with pytest.raises(ValueError): amount('roughly lots')
    with pytest.raises(ValueError): amount('NaN')
    with pytest.raises(ValueError): deadline({'responseDate':'TBD later'})
    assert deadline({'responseDate':'Nov 17, 2026 12:00:00 AM EST'})[:10]=='2026-11-17'


def test_rolling_and_prose_only_expiration():
    raw=item();syn=raw['record']['synopsis']
    syn['responseDateStr']='2076-01-01-00-00-00'
    syn['responseDateDesc']='Proposals accepted anytime'
    r=clean(raw,date(2026,11,17))
    assert r['deadline_parsed'] is None
    assert r['deadline_precision']=='rolling'
    assert r['source_deadline_date'][:10]=='2076-01-01'
    del syn['responseDateStr']
    syn['responseDateDesc']='Full applications by October 3, 2011 or November 2, 2011.'
    assert clean(raw,date(2026,11,17)) is None
    syn['responseDateDesc']='See attached document for details.'
    assert clean(raw,date(2026,11,17)) is None
    syn['responseDateDesc']='Applications due December 1, 2026.'
    assert clean(raw,date(2026,11,17))['deadline_parsed'][:10]=='2026-12-01'


def test_nested_encoded_markup_removed():
    from rigbys_feed.cleaning import text
    assert text('&amp;lt;ul&amp;gt;&amp;lt;li&amp;gt;Eligible&amp;lt;/li&amp;gt;&amp;lt;/ul&amp;gt;')=='Eligible'


def test_literal_ampersand_at_end_is_not_lost_by_html_parser():
    from rigbys_feed.cleaning import text
    title='Research on Science (NCSES S&amp;T)'
    assert text(title)=='Research on Science (NCSES S&T)'
    assert text('A small S&T enterprise')=='A small S&T enterprise'
