from datetime import datetime, timedelta, timezone
from rigbys_feed.builder import research_due, transform
from rigbys_feed.research import default_fiscal_years
from test_cleaning import item


def test_weekly_schedule_and_cold_start():
    now=datetime.now(timezone.utc)
    cache={'fetched_at':(now-timedelta(days=6)).isoformat(),'payload':{'coverage':{'fiscal_years':default_fiscal_years()}}}
    assert not research_due(cache,now)
    cache['fetched_at']=(now-timedelta(days=7)).isoformat()
    assert research_due(cache,now)
    assert research_due(None,now)


def test_all_five_layers_in_transform():
    r=transform([item()],[],[],[],{'fiscal_years':default_fiscal_years()},datetime(2026,11,17,tzinfo=timezone.utc))[0]
    assert r['title_normalized']
    assert r['join_status']=='no_confirmed_award_in_scoped_sources'
    assert r['methodology_version']
    assert r['score_evidence']['status']=='insufficient_data_neutral_placeholder'
    assert r['summary_short'] and r['extracted_requirements']
    assert r['feed_generated_at'] and r['source_refs']
    assert r['linked_trials'] == []
    assert r['linked_nsf_program_awards'] == []
    assert r['score_evidence_detail']['basis'] == 'neutral_placeholder'
