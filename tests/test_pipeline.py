"""Pipeline integration: cadence, failure recovery, timestamps and mutual exclusion."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

from rigbys_feed import builder
from rigbys_feed.database import health, load_cache
from rigbys_feed.sources import SourceError
from test_cleaning import item
from test_database import database  # noqa: F401 -- shared isolated PostgreSQL fixture


def grants():
    timestamp = datetime.now(timezone.utc).isoformat()
    rows = []
    for i in range(100):
        row = deepcopy(item())
        row['record']['id'] = i + 1000
        row['record']['opportunityNumber'] = f'PA-26-{i:03d}'
        row['record']['synopsis']['responseDateStr'] = '2099-12-31-00-00-00'
        row['ref']['fetched_at'] = timestamp
        rows.append(row)
    return rows


def research(http, raw_grants):
    timestamp = datetime.now(timezone.utc).isoformat()
    ref = {'source': 'research_fixture', 'fetched_at': timestamp}
    award = {'record': {'opportunity_number': 'PA-26-000', 'project_num': '1R01AI123456-01',
                        'core_project_num': 'R01AI123456', 'appl_id': 42, 'fiscal_year': 2026}, 'ref': ref}
    paper = {'record': {'id': 'https://openalex.org/W123', 'title': 'Verified fixture',
                        'publication_year': 2025,
                        'awards': [{'funder_award_id': 'R01AI123456'}]}, 'ref': ref}
    return [award], [], [paper], {'fiscal_years': builder.default_fiscal_years()}


def setup_sources(monkeypatch):
    monkeypatch.setattr(builder.GrantsGov, 'fetch', lambda self: grants())
    monkeypatch.setattr(builder, 'fetch_research', research)


def run(database, tmp_path):
    return builder.build(database, tmp_path/'raw', http=object())


def test_daily_grants_weekly_research_and_timestamp(database, tmp_path, monkeypatch):
    setup_sources(monkeypatch)
    calls = []
    def counted(http, raw_grants):
        calls.append(1)
        return research(http, raw_grants)
    monkeypatch.setattr(builder, 'fetch_research', counted)
    first = run(database, tmp_path)
    assert len(calls) == 1
    assert first['source_counts']['published_opportunities'] == 100
    assert first['source_counts']['award_links'] == 1
    assert first['source_counts']['paper_links'] == 1
    for status in first['sources'].values():
        assert datetime.fromisoformat(first['feed_generated_at']) >= datetime.fromisoformat(status['last_success_at'])
    first_cache = load_cache(database, 'research')
    second = run(database, tmp_path)
    assert len(calls) == 1
    assert second['sources']['nih_reporter']['reused_weekly_cache']
    assert second['sources']['openalex']['last_success_at'] == first['sources']['openalex']['last_success_at']
    assert load_cache(database, 'research') == first_cache
    # Expiring the durable cache triggers the next scheduled refresh.
    database.execute("UPDATE source_cache SET fetched_at=%s WHERE cache_name='research'",
                     (datetime.now(timezone.utc)-timedelta(days=8),))
    third = run(database, tmp_path)
    assert len(calls) == 2
    assert not third['sources']['nih_reporter']['reused_weekly_cache']


def test_upstream_failure_preserves_complete_feed_and_releases_lock(database, tmp_path, monkeypatch):
    setup_sources(monkeypatch)
    good = run(database, tmp_path)
    before = database.execute('SELECT opportunity_id, record FROM opportunities ORDER BY opportunity_id').fetchall()
    cache_before = load_cache(database, 'research')
    def fail(self):
        raise SourceError('upstream unavailable')
    monkeypatch.setattr(builder.GrantsGov, 'fetch', fail)
    with pytest.raises(SourceError, match='last good feed retained'):
        run(database, tmp_path)
    state = health(database)
    assert state['last_build_status'] == 'failed'
    assert state['feed_generated_at'] == good['feed_generated_at']
    assert database.execute('SELECT opportunity_id, record FROM opportunities ORDER BY opportunity_id').fetchall() == before
    assert load_cache(database, 'research') == cache_before
    monkeypatch.setattr(builder.GrantsGov, 'fetch', lambda self: grants())
    assert run(database, tmp_path)['last_build_status'] == 'success'


def test_concurrent_builder_refused_before_source_fetch(database, tmp_path, monkeypatch):
    with psycopg.connect(database.info.dsn, autocommit=True) as other:
        other.execute('SELECT pg_advisory_lock(724421702)')
        monkeypatch.setattr(builder.GrantsGov, 'fetch', lambda self: pytest.fail('contending job must not fetch'))
        with pytest.raises(SourceError, match='another feed build'):
            run(database, tmp_path)
        assert database.execute('SELECT count(*) FROM feed_runs').fetchone()[0] == 0
