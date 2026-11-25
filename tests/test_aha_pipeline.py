"""AHA pipeline boundaries against synthetic inputs and disposable native PostgreSQL.

These fixtures do not claim live issuer verification or reproduce a historical
federal snapshot. The adapter is stubbed at its normalized AhaBatch boundary;
source parsing and access failures have their own adapter tests.
"""
from copy import deepcopy
from datetime import datetime, timezone
import gzip
import hashlib
import json
from types import SimpleNamespace

import psycopg
import pytest

from rigbys_feed import builder, database as persistence, snapshot_export
from rigbys_feed.database import health, load_cache
from rigbys_feed.sources import SourceError
from rigbys_mcp import snapshots
from test_database import database  # noqa: F401 -- isolated PostgreSQL fixture
from test_pipeline import grants, research, setup_sources


NOW = datetime(2026, 11, 24, 12, tzinfo=timezone.utc)
STAMP = NOW.isoformat()
SCORE_FIELDS = ('growth_score', 'momentum_score', 'novelty_score', 'gap_score')
RESEARCH_FIELDS = ('links', 'linked_awards', 'linked_papers', 'linked_trials',
                   'linked_nsf_program_awards')


def aha_record(slug='career-development-award'):
    """Minimal source-normalized synthetic record, never Grants.gov-cleaned."""
    source_id = '2027-' + slug
    ref = {'source': 'aha', 'source_id': source_id, 'fetched_at': STAMP,
           'url': 'https://professional.heart.org/en/research-programs/'
                  'aha-funding-opportunities/' + slug,
           'field': 'Synthetic pipeline fixture; not live issuer evidence'}
    fields = ('title_normalized', 'sponsor_normalized', 'description',
              'opportunity_number', 'deadline_parsed', 'deadline_precision',
              'deadline_description', 'eligibility_parsed', 'award_amount_parsed',
              'source_ids', 'dedupe_key', 'fetched_at', 'submission_deadline_at',
              'submission_deadline_local', 'submission_deadline_timezone',
              'deadline_stage', 'application_stages', 'award_amount_basis',
              'award_period_months')
    innovative = slug == 'innovative-project-award'
    return {
        'source': 'aha', 'opportunity_id': 'aha-' + source_id,
        'dedupe_key': hashlib.sha256(('aha|2027|' + slug).encode()).hexdigest(),
        'opportunity_number': 'AHA-' + source_id.upper(),
        'title_normalized': '2027 ' + slug.replace('-', ' ').title(),
        'sponsor_normalized': 'American Heart Association',
        'source_ids': [{'source': 'aha', 'id': source_id}],
        'description': 'Synthetic cardiovascular research program for pipeline verification.',
        'deadline_parsed': '2026-12-09T00:00:00+00:00' if innovative else '2026-12-01T00:00:00+00:00',
        'deadline_precision': 'date',
        'source_deadline_date': '2026-12-09T00:00:00+00:00' if innovative else '2026-12-01T00:00:00+00:00',
        'submission_deadline_at': '2026-12-09T21:00:00+00:00' if innovative else '2026-12-01T21:00:00+00:00',
        'submission_deadline_local': '2026-12-09T15:00:00-06:00' if innovative else '2026-12-01T15:00:00-06:00',
        'submission_deadline_timezone': 'America/Chicago',
        'deadline_stage': 'pre_proposal' if innovative else 'full_application',
        'application_stages': [{
            'stage': 'pre_proposal' if innovative else 'full_application',
            'opens_date': '2026-10-01',
            'deadline_at': '2026-12-09T21:00:00+00:00' if innovative else '2026-12-01T21:00:00+00:00',
            'required': True, 'invitation_required': False,
        }],
        'deadline_description': 'See reviewed program stages and exact Central-time deadline.',
        'eligibility_parsed': ['Eligible US nonprofit host; see full reviewed requirements.'],
        'eligibility_geography': {'country': 'US', 'scope': 'nationwide',
                                  'state_restrictions': [], 'basis': 'Synthetic national fixture.'},
        'award_amount_parsed': {'currency': 'USD', 'floor': None,
                                'ceiling': 200000 if innovative else 231000,
                                'note': 'Total award inclusive of indirect costs.'},
        'award_amount_basis': 'total', 'award_period_months': 24 if innovative else 36,
        'fetched_at': STAMP, 'updated_at': STAMP, 'change_log': [], 'quality_flags': [],
        'source_refs': {field: [deepcopy(ref)] for field in fields},
    }


def batch(records=None):
    values = ([aha_record(), aha_record('innovative-project-award')]
              if records is None else deepcopy(records))
    return SimpleNamespace(
        records=values,
        scope={'source': 'aha', 'reviewed_programs': [
            '2027-career-development-award', '2027-innovative-project-award']},
        references=[deepcopy(aha_record()['source_refs']['title_normalized'][0])],
        verification={'status': 'verified', 'verified_at': STAMP},
        counts={'aha_reviewed_programs': 2, 'aha_admitted_opportunities': len(values),
                'aha_excluded_programs': max(0, 2-len(values))},
    )


def frozen_inputs():
    rows = grants()
    for row in rows:
        row['ref']['fetched_at'] = STAMP
        row['ref']['source'] = 'grants_gov'
    awards, publications, papers, coverage = research(None, rows)
    for wrapped in awards + publications + papers:
        wrapped['ref']['fetched_at'] = STAMP
    trials = {'NCT01234567': {'nct_id': 'NCT01234567', 'title': 'Synthetic study',
              'status': 'COMPLETED', 'nih_ids': {'1R01AI123456-01': 'R01AI123456'},
              'ref': {'source': 'clinical_trials_gov', 'fetched_at': STAMP}}}
    return (rows, awards, publications, papers, coverage), trials


@pytest.fixture
def federal_sources(monkeypatch):
    setup_sources(monkeypatch)
    inputs, trials = frozen_inputs()
    rows, awards, publications, papers, coverage = inputs
    calls = {'research': 0, 'trials': 0}

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW if tz is not None else NOW.replace(tzinfo=None)

    def fixed_research(_http, _grants):
        calls['research'] += 1
        return deepcopy((awards, publications, papers, coverage))

    def fixed_trials(_self):
        calls['trials'] += 1
        return deepcopy(trials), STAMP

    monkeypatch.setattr(builder, 'datetime', FrozenDateTime)
    monkeypatch.setattr(builder.GrantsGov, 'fetch', lambda _self: deepcopy(rows))
    monkeypatch.setattr(builder, 'fetch_research', fixed_research)
    monkeypatch.setattr(builder.ClinicalTrials, 'nih_studies', fixed_trials)
    return rows, calls


def build(conn, tmp_path, *, enabled=True, **kwargs):
    return builder.build(conn, tmp_path/'raw', http=object(),
                         aha_manifest=tmp_path/'synthetic-reviewed.json' if enabled else None,
                         **kwargs)


def published_state(conn):
    """Full row/custody/export equality, allowing only a new failed attempt."""
    orders = {'opportunities': 'opportunity_id',
              'opportunity_links': 'opportunity_id,link_type,target_id',
              'source_cache': 'cache_name', 'free_feed_snapshots': 'snapshot_id',
              'free_search_records': 'snapshot_id,opportunity_id',
              'snapshot_exports': 'slot', 'snapshot_export_chunks': 'run_id,chunk_index'}
    result = {name: conn.execute('SELECT * FROM '+name+' ORDER BY '+order).fetchall()
              for name, order in orders.items()}
    result['successful_runs'] = conn.execute(
        "SELECT * FROM feed_runs WHERE status='success' ORDER BY run_id").fetchall()
    result['generated_at'] = health(conn)['feed_generated_at']
    result['counts'] = health(conn)['source_counts']
    return result


def test_additional_records_preserve_every_frozen_federal_field():
    inputs, trials = frozen_inputs()
    # Include independently joined NSF context in the invariance comparison.
    inputs[0][-1]['record']['opportunityNumber'] = '25-531'
    inputs[0][-1]['record']['agencyDetails'] = {
        'agencyName': 'U.S. National Science Foundation', 'topAgencyCode': 'NSF'}
    nsf = {'25-531': {'fetched_at': STAMP, 'source_results': 1, 'awards': [
        {'id': '1234567', 'title': 'Synthetic NSF award', 'source_award_date': '01/01/2026',
         'matched_program_codes': ['802700'],
         'ref': {'source': 'nsf_award_search', 'fetched_at': STAMP}}]}}
    original = deepcopy(inputs)
    baseline = builder.transform(*deepcopy(inputs), NOW, trials=deepcopy(trials),
                                 nsf_programs=deepcopy(nsf))
    additional = batch().records
    untouched = deepcopy(additional)
    combined = builder.transform(*deepcopy(inputs), NOW, trials=deepcopy(trials),
                                 nsf_programs=deepcopy(nsf), additional_records=additional)
    assert len(baseline) == 100 and len(combined) == 102
    assert [r for r in combined if r['opportunity_id'].startswith('gg-')] == baseline
    assert inputs == original and additional == untouched
    assert baseline[0]['linked_awards'] and baseline[0]['linked_papers']
    assert baseline[0]['linked_trials'] and baseline[-1]['linked_nsf_program_awards']


@pytest.mark.parametrize('number', ['PA-26-000', '25-531'])
def test_number_collision_never_joins_aha_to_federal_research(number):
    inputs, trials = frozen_inputs()
    inputs[0][-1]['record']['opportunityNumber'] = '25-531'
    inputs[0][-1]['record']['agencyDetails'] = {
        'agencyName': 'U.S. National Science Foundation', 'topAgencyCode': 'NSF'}
    nsf = {'25-531': {'fetched_at': STAMP, 'source_results': 1, 'awards': [
        {'id': '1234567', 'title': 'Synthetic NSF award', 'source_award_date': '01/01/2026',
         'matched_program_codes': ['802700'],
         'ref': {'source': 'nsf_award_search', 'fetched_at': STAMP}}]}}
    incoming = aha_record()
    incoming['opportunity_number'] = number
    records = builder.transform(*inputs, NOW, trials=trials,
                                nsf_programs=nsf, additional_records=[incoming])
    federal = next(r for r in records if r['opportunity_number'] == number
                   and r['opportunity_id'].startswith('gg-'))
    assert federal['linked_awards'] if number.startswith('PA-') else federal['linked_nsf_program_awards']
    added = next(r for r in records if r['opportunity_id'].startswith('aha-'))
    assert all(added[field] == [] for field in RESEARCH_FIELDS)
    assert added['research_coverage']['status'] == 'outside_current_research_coverage'
    assert added['join_status'] == 'outside_current_research_coverage'
    assert {added[field] for field in SCORE_FIELDS} == {50}
    assert added['score_evidence']['status'] == 'insufficient_data_neutral_placeholder'
    assert added['score_evidence_detail']['basis'] == 'neutral_placeholder'
    assert 'absence is not evidence of a research gap' in added['research_coverage']['note']
    assert not any(x['source'] in {'nih_reporter', 'openalex', 'clinical_trials_gov', 'nsf_award_search'}
                   for x in added['source_ids'])
    assert added['summary_short'] and added['extracted_requirements'] == added['eligibility_parsed'] + [
        'Source deadline requirements: '+added['deadline_description']]


@pytest.mark.parametrize('field', RESEARCH_FIELDS)
def test_normalized_aha_cannot_smuggle_research_links(field):
    inputs, _ = frozen_inputs()
    incoming = aha_record()
    incoming[field] = [{'target_id': 'invented-link'}]
    with pytest.raises(SourceError, match='outside the implemented coverage'):
        builder.transform(*inputs, NOW, additional_records=[incoming])


def test_default_disabled_build_has_no_aha_calls(database, tmp_path, monkeypatch, federal_sources):
    monkeypatch.delenv('RIGBYS_AHA_MANIFEST', raising=False)
    monkeypatch.setattr(builder.aha, 'collect', lambda *_a, **_k: pytest.fail('disabled source requested'))
    result = build(database, tmp_path, enabled=False)
    assert result['source_counts']['published_opportunities'] == 100
    assert 'aha' not in result['sources']
    assert load_cache(database, 'aha_scope') is None
    assert database.execute("SELECT count(*) FROM opportunities WHERE starts_with(opportunity_id,'aha-')").fetchone() == (0,)


def test_two_builds_are_idempotent_102_and_reuse_weekly_federal_cache(
    database, tmp_path, monkeypatch, federal_sources,
):
    rows, calls = federal_sources
    invocations = []

    def collected(*args):
        invocations.append(args)
        return batch()

    monkeypatch.setattr(builder.aha, 'collect', collected)
    first = build(database, tmp_path)
    first_rows = database.execute('SELECT * FROM opportunities ORDER BY opportunity_id').fetchall()
    first_cache = load_cache(database, 'research')
    second = build(database, tmp_path)
    assert first['source_counts']['published_opportunities'] == 102
    assert second['source_counts']['published_opportunities'] == 102
    assert second['source_counts']['grants_gov_posted'] == 100
    assert second['source_counts']['excluded_or_deduped'] == 0
    assert second['source_counts']['aha_reviewed_programs'] == 2
    assert second['source_counts']['aha_admitted_opportunities'] == 2
    assert second['source_counts']['aha_excluded_programs'] == 0
    assert len(invocations) == 2  # AHA is freshly collected, never a weekly-cache freshness claim.
    assert calls == {'research': 1, 'trials': 1}
    assert second['sources']['nih_reporter']['reused_weekly_cache']
    assert second['sources']['clinical_trials_gov']['reused_weekly_cache']
    assert load_cache(database, 'research') == first_cache
    assert database.execute('SELECT * FROM opportunities ORDER BY opportunity_id').fetchall() == first_rows
    assert database.execute('SELECT count(DISTINCT opportunity_id),count(DISTINCT dedupe_key) FROM opportunities').fetchone() == (102, 102)
    for (record,) in database.execute("SELECT record FROM opportunities WHERE starts_with(opportunity_id,'aha-')"):
        assert record['change_log'] == []
        assert all(record[field] == [] for field in RESEARCH_FIELDS if field != 'links')
        assert {record[field] for field in SCORE_FIELDS} == {50}
    assert database.execute("SELECT count(*) FROM opportunity_links WHERE starts_with(opportunity_id,'aha-')").fetchone() == (0,)
    current = database.execute("SELECT run_id FROM snapshot_exports WHERE slot='current'").fetchone()[0]
    compressed = b''.join(row[0] for row in database.execute(
        'SELECT data FROM snapshot_export_chunks WHERE run_id=%s ORDER BY chunk_index', (current,)))
    exported = json.loads(gzip.decompress(compressed))
    assert exported['record_count'] == 102
    assert len({r['opportunity_id'] for r in exported['opportunities']}) == 102


def test_aha_never_satisfies_federal_minimum(database, tmp_path, monkeypatch, federal_sources):
    rows, _ = federal_sources
    monkeypatch.setattr(builder.GrantsGov, 'fetch', lambda _self: deepcopy(rows[:98]))
    monkeypatch.setattr(builder.aha, 'collect', lambda *_a: pytest.fail('federal minimum must fail first'))
    with pytest.raises(SourceError, match='grants_gov; last good feed retained'):
        build(database, tmp_path)
    assert database.execute('SELECT count(*) FROM opportunities').fetchone() == (0,)
    assert database.execute("SELECT count(*) FROM feed_runs WHERE status='success'").fetchone() == (0,)


def test_federal_exclusion_counts_do_not_subtract_aha(database, tmp_path, monkeypatch, federal_sources):
    rows, _ = federal_sources
    rows[98]['record']['synopsis']['responseDateStr'] = '2000-01-01-00-00-00'
    rows[99]['record']['opportunityNumber'] = rows[97]['record']['opportunityNumber']
    monkeypatch.setattr(builder.aha, 'collect', lambda *_a: batch())
    result = build(database, tmp_path)
    assert result['source_counts']['grants_gov_posted'] == 100
    assert result['source_counts']['excluded_or_deduped'] == 2
    assert result['source_counts']['published_opportunities'] == 100  # 98 federal + 2 AHA.
    assert result['source_counts']['aha_admitted_opportunities'] == 2


def test_aha_cannot_hide_an_empty_cleaned_federal_candidate(
    database, tmp_path, monkeypatch, federal_sources,
):
    monkeypatch.setattr(builder.aha, 'collect', lambda *_a: batch())
    build(database, tmp_path)
    before = published_state(database)
    rows, _ = federal_sources
    for row in rows:
        row['record']['synopsis']['responseDateStr'] = '2000-01-01-00-00-00'
    with pytest.raises(SourceError, match='candidate_validation; last good feed retained'):
        build(database, tmp_path)
    assert published_state(database) == before


def test_aha_deadline_is_rechecked_at_transform_after_collect_straddles_closure(
    database, tmp_path, monkeypatch, federal_sources,
):
    before = datetime(2026, 12, 1, 20, 59, 59, tzinfo=timezone.utc)
    closed = datetime(2026, 12, 1, 21, tzinfo=timezone.utc)
    ticks = []

    class StraddlingDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            ticks.append(1)
            return before if len(ticks) < 3 else closed

    verified = batch()
    verified.verification['verified_at'] = before.isoformat()
    for ref in verified.references:
        ref['fetched_at'] = before.isoformat()
    monkeypatch.setattr(builder, 'datetime', StraddlingDateTime)
    monkeypatch.setattr(builder.aha, 'collect', lambda *_a: deepcopy(verified))
    result = build(database, tmp_path)
    assert result['feed_generated_at'] == closed.isoformat()
    assert result['source_counts']['aha_admitted_opportunities'] == 1
    assert result['source_counts']['aha_excluded_programs'] == 1
    assert database.execute("SELECT opportunity_id FROM opportunities WHERE starts_with(opportunity_id,'aha-')").fetchall() == [
        ('aha-2027-innovative-project-award',)]


@pytest.mark.parametrize('status', ['manual_review', 'unverified', None])
def test_unverified_enabled_batch_is_not_a_successful_empty_source(
    database, tmp_path, monkeypatch, federal_sources, status,
):
    monkeypatch.setattr(builder.aha, 'collect', lambda *_a: batch())
    build(database, tmp_path)
    before = published_state(database)
    unverified = batch([])
    if status is None:
        unverified.verification.pop('status')
    else:
        unverified.verification['status'] = status
    monkeypatch.setattr(builder.aha, 'collect', lambda *_a: deepcopy(unverified))
    with pytest.raises(SourceError, match='aha; last good feed retained'):
        build(database, tmp_path)
    assert published_state(database) == before


def test_refetch_metadata_changes_do_not_manufacture_substantive_changes(
    database, tmp_path, monkeypatch, federal_sources,
):
    first = batch()
    for incoming in first.records:
        for refs in incoming['source_refs'].values():
            for ref in refs:
                ref.update(sha256='a'*64, raw_path='/synthetic/first/envelope.json',
                           content_sha256='c'*64)
    monkeypatch.setattr(builder.aha, 'collect', lambda *_a: deepcopy(first))
    initial = build(database, tmp_path)
    prior = dict(database.execute("SELECT opportunity_id,record FROM opportunities WHERE starts_with(opportunity_id,'aha-')").fetchall())
    later = datetime(2026, 11, 25, 12, tzinfo=timezone.utc)

    class NextDayDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return later

    refetched = deepcopy(first)
    refetched.verification['verified_at'] = later.isoformat()
    for ref in refetched.references:
        ref['fetched_at'] = later.isoformat()
    for incoming in refetched.records:
        incoming['fetched_at'] = incoming['updated_at'] = later.isoformat()
        for refs in incoming['source_refs'].values():
            for ref in refs:
                ref.update(fetched_at=later.isoformat(), sha256='b'*64,
                           raw_path='/synthetic/second/envelope.json')
    monkeypatch.setattr(builder, 'datetime', NextDayDateTime)
    monkeypatch.setattr(builder.aha, 'collect', lambda *_a: deepcopy(refetched))
    second = build(database, tmp_path)
    assert second['feed_generated_at'] != initial['feed_generated_at']
    assert second['sources']['aha']['last_success_at'] == later.isoformat()
    current = dict(database.execute("SELECT opportunity_id,record FROM opportunities WHERE starts_with(opportunity_id,'aha-')").fetchall())
    assert current.keys() == prior.keys()
    for identifier, record in current.items():
        assert record['dedupe_key'] == prior[identifier]['dedupe_key']
        assert record['fetched_at'] == later.isoformat()
        assert record['feed_generated_at'] == later.isoformat()
        assert record['updated_at'] == prior[identifier]['updated_at']
        assert record['change_log'] == prior[identifier]['change_log'] == []
        refs = record['source_refs']['title_normalized']
        assert refs[0]['sha256'] == 'b'*64 and refs[0]['content_sha256'] == 'c'*64


@pytest.mark.parametrize('field', ['opportunity_id', 'dedupe_key'])
def test_candidate_validation_independently_rejects_duplicate_identity(field):
    inputs, _ = frozen_inputs()
    records = builder.transform(*inputs, NOW, additional_records=batch().records)
    records[-1][field] = records[0][field]
    with pytest.raises(SourceError, match='duplicate opportunity identity'):
        builder.validate_candidate(records)


def test_forged_aha_dedupe_key_is_rejected_at_the_normalized_boundary():
    inputs, _ = frozen_inputs()
    incoming = aha_record()
    incoming['dedupe_key'] = '0'*64
    with pytest.raises(SourceError, match='Invalid normalized AHA deduplication key'):
        builder.transform(*inputs, NOW, additional_records=[incoming])


@pytest.mark.parametrize('empty', [False, True])
def test_published_scope_cannot_disappear_even_after_verified_expiry(
    database, tmp_path, monkeypatch, federal_sources, empty,
):
    monkeypatch.setattr(builder.aha, 'collect', lambda *_a: batch())
    build(database, tmp_path)
    if empty:
        # Represents fresh verification that both reviewed entry gates closed.
        monkeypatch.setattr(builder.aha, 'collect', lambda *_a: batch([]))
        good = build(database, tmp_path)
        assert good['source_counts']['aha_admitted_opportunities'] == 0
        assert database.execute("SELECT count(*) FROM opportunities WHERE starts_with(opportunity_id,'aha-')").fetchone() == (0,)
    assert load_cache(database, 'aha_scope')['payload'] == batch().scope
    before = published_state(database)
    monkeypatch.setattr(builder.GrantsGov, 'fetch', lambda _self: pytest.fail('configuration guard must precede fetch'))
    with pytest.raises(SourceError, match='source_configuration; last good feed retained'):
        build(database, tmp_path, enabled=False)
    assert published_state(database) == before


def test_existing_aha_rows_guard_omission_when_scope_marker_is_missing(
    database, tmp_path, monkeypatch, federal_sources,
):
    monkeypatch.setattr(builder.aha, 'collect', lambda *_a: batch())
    build(database, tmp_path)
    # Models an earlier compatible publisher's rows, without its durable marker.
    database.execute("DELETE FROM source_cache WHERE cache_name='aha_scope'")
    before = published_state(database)
    assert load_cache(database, 'aha_scope') is None
    monkeypatch.setattr(builder.GrantsGov, 'fetch', lambda _self: pytest.fail('must reject omission before fetch'))
    with pytest.raises(SourceError, match='source_configuration; last good feed retained'):
        build(database, tmp_path, enabled=False)
    assert published_state(database) == before


@pytest.mark.parametrize('identity', ['duplicate_id', 'canonical_id', 'federal_source_id',
                                     'federal_url', 'federal_canonical_url'])
def test_actual_candidate_identity_conflicts_retain_federal_canonical(
    database, tmp_path, monkeypatch, federal_sources, identity,
):
    monkeypatch.setattr(builder.aha, 'collect', lambda *_a: batch())
    build(database, tmp_path)
    before = published_state(database)
    added = batch().records
    if identity == 'duplicate_id':
        added.append(deepcopy(added[0]))
    elif identity == 'canonical_id':
        added[0]['canonical_opportunity_id'] = 'gg-1000'
    elif identity == 'federal_source_id':
        added[0]['source_ids'].append({'source': 'grants_gov', 'id': '1000'})
    else:
        field = 'url' if identity == 'federal_url' else 'canonical_url'
        added[0]['source_refs']['title_normalized'][0][field] = 'https://www.grants.gov/search-results-detail/1000'
    monkeypatch.setattr(builder.aha, 'collect', lambda *_a: batch(added))
    with pytest.raises(SourceError, match='candidate_validation; last good feed retained'):
        build(database, tmp_path)
    assert published_state(database) == before


def test_title_amount_date_similarity_is_not_mirror_evidence(
    database, tmp_path, monkeypatch, federal_sources,
):
    rows, _ = federal_sources
    added = batch().records
    # Align all superficial fields on a synthetic federal record, without
    # changing the normalized AHA program's true stage/amount/date relationship.
    rows[0]['record']['opportunityTitle'] = added[0]['title_normalized']
    rows[0]['record']['synopsis'].update(responseDateStr='2026-12-01-00-00-00',
                                       awardFloor=None, awardCeiling='231000')
    monkeypatch.setattr(builder.aha, 'collect', lambda *_a: batch(added))
    good = build(database, tmp_path)
    assert good['source_counts']['published_opportunities'] == 102
    assert database.execute('SELECT count(*) FROM opportunities WHERE title_normalized=%s',
                            (added[0]['title_normalized'],)).fetchone() == (2,)


@pytest.mark.parametrize('failure', ['aha', 'insert', 'cache', 'snapshot', 'export'])
def test_failed_enabled_build_preserves_complete_feed_custody_and_export(
    database, tmp_path, monkeypatch, federal_sources, caplog, failure,
):
    monkeypatch.setattr(builder.aha, 'collect', lambda *_a: batch())
    monkeypatch.setattr(snapshot_export, '_CHUNK_BYTES', 512)
    build(database, tmp_path)
    build(database, tmp_path)
    assert database.execute('SELECT count(*) FROM snapshot_exports').fetchone() == (2,)
    assert database.execute('SELECT min(chunk_count) FROM snapshot_exports').fetchone()[0] > 1
    before = published_state(database)
    # The next candidate really changes rows, removes a record and its research
    # graph, and changes the scope cache; equality cannot pass vacuously.
    rows, _ = federal_sources
    rows[0]['record']['opportunityTitle'] = 'Changed before the failed publication'
    rows[0]['record']['opportunityNumber'] = 'PA-26-NEW'
    rows[-1]['record']['synopsis']['responseDateStr'] = '2000-01-01-00-00-00'
    changed = batch()
    changed.scope['manifest_sha256'] = 'b'*64
    changed.records[0]['title_normalized'] = 'Changed AHA candidate title'
    monkeypatch.setattr(builder.aha, 'collect', lambda *_a: deepcopy(changed))
    secret = 'https://private.invalid/?password=do-not-log'
    with monkeypatch.context() as patch:
        if failure == 'aha':
            def fail_aha(*_args):
                raise SourceError(secret)
            patch.setattr(builder.aha, 'collect', fail_aha)
        elif failure == 'insert':
            database.execute("""CREATE FUNCTION fail_aha_pipeline_insert() RETURNS trigger
                LANGUAGE plpgsql AS $$ BEGIN
                IF NEW.opportunity_id='gg-1003' THEN RAISE EXCEPTION 'synthetic insert failure'; END IF;
                RETURN NEW; END $$""")
            database.execute('''CREATE TRIGGER fail_aha_pipeline_insert BEFORE INSERT OR UPDATE
                ON opportunities FOR EACH ROW EXECUTE FUNCTION fail_aha_pipeline_insert()''')
        elif failure == 'cache':
            save = persistence._save_cache
            def fail_cache(conn, name, value):
                save(conn, name, value)
                if name == 'aha_scope':
                    raise RuntimeError(secret)
            patch.setattr(persistence, '_save_cache', fail_cache)
        elif failure == 'snapshot':
            capture = snapshots.capture_snapshot
            def fail_snapshot(conn, run_id):
                capture(conn, run_id)
                raise RuntimeError(secret)
            patch.setattr(snapshots, 'capture_snapshot', fail_snapshot)
        else:
            chunks = snapshot_export._fixed_chunks
            def partial_export(parts):
                yield next(chunks(parts))
                raise RuntimeError(secret)
            patch.setattr(snapshot_export, '_fixed_chunks', partial_export)
        with pytest.raises(SourceError, match='last good feed retained') as error:
            build(database, tmp_path, force_research=True)
        assert secret not in str(error.value)
        assert secret not in caplog.text
    assert published_state(database) == before
    assert health(database)['last_build_status'] == 'failed'
    assert health(database)['last_failure']['failed_stage'] == ('aha' if failure == 'aha' else 'postgres_publication')
    assert database.execute("SELECT count(*) FROM feed_runs WHERE status='failed'").fetchone() == (1,)
    # The retained free snapshots are still sealed, not merely equal just now.
    with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState, match='immutable'):
        database.execute("UPDATE free_search_records SET title_normalized='must not change'")
    assert published_state(database) == before
    if failure == 'insert':
        database.execute('DROP TRIGGER fail_aha_pipeline_insert ON opportunities')
        database.execute('DROP FUNCTION fail_aha_pipeline_insert()')
    # All fault paths release the advisory lock and permit a complete next run.
    assert build(database, tmp_path)['last_build_status'] == 'success'
