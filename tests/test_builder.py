from datetime import datetime, timedelta, timezone
import json
from unittest.mock import Mock

import pytest

from rigbys_feed import builder, cli
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


def test_failure_event_has_readable_railway_message(tmp_path, monkeypatch, caplog):
    conn = Mock()
    conn.execute.return_value.fetchone.return_value = (True,)
    monkeypatch.setattr(builder, 'health', lambda _: {'sources': {}})
    monkeypatch.setattr(builder, 'record_failure', Mock())

    def fail(_):
        raise TypeError('sensitive upstream payload')

    monkeypatch.setattr(builder.GrantsGov, 'fetch', fail)
    with pytest.raises(builder.SourceError):
        builder.build(conn, tmp_path, http=object())

    event = json.loads(caplog.records[-1].getMessage())
    assert event['event'] == 'feed_build_failed'
    assert event['failed_stage'] == 'grants_gov'
    assert event['error_type'] == 'TypeError'
    assert event['level'] == 'error'
    assert event['message'] == 'Feed build failed at grants_gov (TypeError)'
    assert 'sensitive upstream payload' not in caplog.text


def test_startup_failure_has_redacted_railway_message(monkeypatch, capsys):
    monkeypatch.setattr(cli.sys, 'argv', ['rigbys-feed', 'build'])
    monkeypatch.setenv('DATABASE_URL', 'postgresql://example.test/feed')
    monkeypatch.setattr(cli.psycopg, 'connect', Mock(side_effect=OSError('sensitive DSN')))

    assert cli.main() == 1

    output = capsys.readouterr().err
    error = json.loads(output)
    assert error['status'] == 'failed'
    assert error['error_type'] == 'OSError'
    assert error['level'] == 'error'
    assert error['message'] == 'Feed command failed (OSError)'
    assert 'sensitive DSN' not in output
