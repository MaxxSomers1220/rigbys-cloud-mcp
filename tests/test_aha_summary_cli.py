"""Additive summary/CLI behavior without changing federal summaries or commands."""
from copy import deepcopy
from datetime import date
from unittest.mock import MagicMock

import pytest

from rigbys_feed import cli
from rigbys_feed.cleaning import clean
from rigbys_feed.summarizing import summarize
from test_cleaning import item


def staged_record():
    record = clean(item(), date(2026, 11, 24))
    record.update(
        deadline_stage='pre_proposal',
        deadline_parsed='2026-12-09T00:00:00+00:00',
        submission_deadline_at='2026-12-09T21:00:00+00:00',
        submission_deadline_local='2026-12-09T15:00:00-06:00',
        submission_deadline_timezone='America/Chicago',
        application_stages=[
            {'stage': 'pre_proposal', 'required': True, 'invitation_required': False,
             'deadline_at': '2026-12-09T21:00:00+00:00'},
            {'stage': 'full_application', 'required': True, 'invitation_required': True,
             'deadline_at': '2027-03-04T21:00:00+00:00'},
        ],
        award_amount_basis='total', award_period_months=24,
        award_amount_parsed={'currency': 'USD', 'floor': None, 'ceiling': 200000,
                             'note': 'Includes the source-stated indirect costs.'},
    )
    for field in ('deadline_stage', 'submission_deadline_at', 'submission_deadline_local',
                  'submission_deadline_timezone', 'application_stages', 'award_amount_basis',
                  'award_period_months'):
        record['source_refs'][field] = [{'source': 'aha', 'field': field, 'url': 'https://example.test/fixture'}]
    return record


def test_summary_preserves_first_entry_gate_and_total_with_all_new_claims_cited():
    record = summarize(staged_record())
    summary = record['summary_short']
    assert summary.index('pre proposal') < summary.index('full application')
    assert '2026-12-09T15:00:00-06:00' in summary
    assert 'America/Chicago' in summary and '2026-12-09T21:00:00+00:00' in summary
    assert 'Invited applicants only' in summary and '2027-03-04' in summary
    assert 'does not extend entry for new applicants' in summary
    assert '$200,000.00 over 24 months' in summary and '$220,000' not in summary
    assert 'indirect costs' in summary
    cited = {reference.get('field') for reference in record['source_refs']['summary_short']}
    for field in ('deadline_stage', 'submission_deadline_at', 'submission_deadline_local',
                  'submission_deadline_timezone', 'application_stages', 'award_amount_basis',
                  'award_period_months'):
        assert field in cited


def test_federal_summary_stays_identical_when_additive_fields_are_absent():
    original = clean(item(), date(2026, 11, 24))
    result = summarize(deepcopy(original))
    assert 'Next required action' not in result['summary_short']
    assert 'Source closing date: 2027-01-02 (date only;' in result['summary_short']
    assert result['source_refs']['summary_short'] == (
        original['source_refs']['description'] + original['source_refs']['sponsor_normalized'] +
        original['source_refs']['deadline_parsed'] + original['source_refs']['deadline_description'] +
        original['source_refs']['award_amount_parsed'] + original['source_refs']['eligibility_parsed'])


@pytest.mark.parametrize('argument,environment,expected', [
    (None, None, None), (None, '/reviewed/environment.json', '/reviewed/environment.json'),
    ('/reviewed/explicit.json', '/reviewed/environment.json', '/reviewed/explicit.json'),
])
def test_cli_manifest_is_optional_environment_default_and_explicit_override(
        monkeypatch, capsys, argument, environment, expected):
    monkeypatch.setenv('DATABASE_URL', 'postgresql://disposable.invalid/fixture')
    monkeypatch.delenv('RIGBYS_AHA_MANIFEST', raising=False)
    if environment:
        monkeypatch.setenv('RIGBYS_AHA_MANIFEST', environment)
    argv = ['rigbys-feed', 'build'] + (['--aha-manifest', argument] if argument else [])
    monkeypatch.setattr(cli.sys, 'argv', argv)
    connection = MagicMock()
    monkeypatch.setattr(cli.psycopg, 'connect', lambda *args, **kwargs: connection)
    monkeypatch.setattr(cli, 'migrate', lambda conn: None)
    calls = []
    monkeypatch.setattr(cli, 'build', lambda *args, **kwargs: calls.append((args, kwargs)) or {'status': 'fixture'})
    assert cli.main() == 0
    assert len(calls) == 1 and len(calls[0][0]) == 4
    assert calls[0][1] == {'aha_manifest': expected}
    assert 'fixture' in capsys.readouterr().out
