"""Scheduled feed pipeline. Publication is atomic; upstream failure never erases a feed."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
from pathlib import Path

from .cleaning import clean_all
from .clinical_trials import ClinicalTrials, attach_trials, mentioned_ids
from .database import health, load_cache, publish_feed, record_failure
from .joining import join
from .nsf import PROGRAMS, NsfAwardSearch, attach_nsf_awards, opportunity_numbers
from .research import fetch_research, default_fiscal_years
from .scoring import score
from .sources import GrantsGov, PublicClient, SourceError, utcnow
from .summarizing import summarize

log = logging.getLogger(__name__)


class ResumeClient(PublicClient):
    """Opt-in recovery of today's successful public requests, keeping original timestamps.

    Never uses older-than-12-hour data, and revalidates archived hashes. This is
    useful after a long source refresh is interrupted. Normal scheduled runs do
    not enable this option; weekly reuse is handled by the durable database cache.
    """
    def __init__(self, raw_dir):
        super().__init__(raw_dir)
        self.saved = {}
        cutoff = datetime.now(timezone.utc) - timedelta(hours=12)
        for path in Path(raw_dir).glob('*/*.json'):
            envelope = json.loads(path.read_text())
            stamp = datetime.fromisoformat(envelope['fetched_at'])
            if stamp < cutoff:
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != path.stem:
                raise SourceError('raw archive checksum mismatch')
            key = json.dumps([envelope['source'], envelope['url'], envelope['request']], sort_keys=True)
            ref = {'source':envelope['source'], 'url':envelope['url'],
                   'fetched_at':envelope['fetched_at'], 'raw_path':str(path), 'sha256':digest}
            if key not in self.saved or stamp > datetime.fromisoformat(self.saved[key][1]['fetched_at']):
                self.saved[key] = envelope['response'], ref

    def request(self, source, method, url, **kwargs):
        # These clients use a single method per source URL; kwargs include all query criteria.
        key = json.dumps([source, url, kwargs], sort_keys=True)
        return self.saved[key] if key in self.saved else super().request(source, method, url, **kwargs)


def research_due(cache, now):
    if not cache:
        return True
    last = datetime.fromisoformat(cache['fetched_at'])
    return (now-last >= timedelta(days=7) or
            cache['payload']['coverage'].get('fiscal_years') != default_fiscal_years())


def weekly_due(cache, now):
    return not cache or now - datetime.fromisoformat(cache['fetched_at']) >= timedelta(days=7)


def compact_research(awards, papers):
    """Cache only fields consumed by this feed; complete source responses stay archived."""
    keys = ('opportunity_number','project_num','core_project_num','appl_id','subproject_id',
            'fiscal_year','award_amount','project_title')
    cores = {a['record']['core_project_num'].strip().upper() for a in awards}
    awards = [{'record':{k:a['record'].get(k) for k in keys}, 'ref':a['ref']} for a in awards]
    paper_keys = ('id','ids','title','display_name','publication_year','publication_date')
    papers = [{'record':{**{k:p['record'].get(k) for k in paper_keys},
                'awards':[{'funder_award_id':a['funder_award_id']} for a in p['record'].get('awards',[])
                          if a.get('funder_award_id','').strip().upper() in cores]},
               'ref':p['ref']} for p in papers]
    return awards, papers


def transform(grants, awards, publications, papers, coverage, now, *, trials=None, nsf_programs=None):
    records = clean_all(grants, now.date())
    join(records, awards, publications, papers, coverage)
    attach_trials(records, trials or {})
    attach_nsf_awards(records, nsf_programs or {})
    for record in records:
        score(record, now.date())
        summarize(record)
        if not record['title_normalized'] or not record['sponsor_normalized']:
            raise SourceError('Candidate record missing normalized title or sponsor')
        record['feed_generated_at'] = now.isoformat()
        record['source_refs']['feed_generated_at'] = [{'builder':'rigbys-feed-0.1.0',
            'generated_at':now.isoformat(), 'note':'Transformation time; source retrieval times remain per field.'}]
    return records


def build(conn, raw_dir, force_research=False, resume_raw=False, http=None):
    now = datetime.now(timezone.utc)
    counts, stage = {}, 'grants_gov'
    statuses = health(conn).get('sources', {})
    if not conn.execute('SELECT pg_try_advisory_lock(724421702)').fetchone()[0]:
        raise SourceError('another feed build is running')
    try:
        http = http or (ResumeClient(raw_dir) if resume_raw else PublicClient(raw_dir))
        grants = GrantsGov(http).fetch()
        counts['grants_gov_posted'] = len(grants)
        statuses['grants_gov'] = {'status':'ok', 'last_success_at':max(x['ref']['fetched_at'] for x in grants)}
        if len(grants) < 100:
            raise SourceError('grants_gov: fewer than 100 posted records; review source before publishing')
        cache = load_cache(conn, 'research')
        stage = 'nih_reporter_openalex'
        refresh = force_research or research_due(cache, now)
        caches = {}
        if refresh:
            awards, publications, papers, coverage = fetch_research(http, grants)
            if not awards or not papers:
                raise SourceError('research: empty source collection; refusing incomplete build')
            awards, papers = compact_research(awards, papers)
            # The oldest source response in this collection governs weekly freshness.
            source_time = min(x['ref']['fetched_at'] for x in awards+papers)
            payload = {'awards':awards, 'publications':publications, 'papers':papers, 'coverage':coverage}
            caches['research'] = {'payload':payload, 'fetched_at':source_time}
        else:
            payload = cache['payload']
            awards, publications, papers, coverage = (payload[k] for k in ('awards','publications','papers','coverage'))
        counts.update(nih_reporter_awards=len(awards), nih_reporter_publications=len(publications),
                      openalex_papers=len(papers))
        stage = 'clinical_trials_gov'
        registry = ClinicalTrials(http)
        trial_cache = load_cache(conn, stage)
        trial_refresh = force_research or weekly_due(trial_cache, now)
        if trial_refresh:
            studies, trial_time = registry.nih_studies()
            caches[stage] = {'payload': studies, 'fetched_at': trial_time}
        else:
            studies, trial_time = trial_cache['payload'], trial_cache['fetched_at']
        explicit_ncts = {nct for grant in grants for nct in mentioned_ids(grant['record'])}
        direct_studies = registry.studies_by_id(explicit_ncts - studies.keys())
        trials = {**studies, **direct_studies}
        counts['clinical_trials_studies'] = len(trials)
        stage = 'nsf_award_search'
        nsf_programs = {}
        nsf_status = {}
        nsf_scope = {number: PROGRAMS[number][1] for number in sorted(opportunity_numbers(grants))}
        if nsf_scope:
            nsf_cache = load_cache(conn, stage)
            nsf_refresh = (force_research or weekly_due(nsf_cache, now)
                           or nsf_cache['payload']['scope'] != nsf_scope)
            if nsf_refresh:
                nsf_programs = NsfAwardSearch(http).awards(nsf_scope)
                stamp = min(program['fetched_at'] for program in nsf_programs.values())
                caches[stage] = {'payload': {'scope': nsf_scope, 'programs': nsf_programs},
                                 'fetched_at': stamp}
            else:
                nsf_programs = nsf_cache['payload']['programs']
                stamp = nsf_cache['fetched_at']
            nsf_status[stage] = {'status': 'ok', 'oldest_response_at': stamp,
                                 'last_success_at': max(p['fetched_at'] for p in nsf_programs.values()),
                                 'reused_weekly_cache': not nsf_refresh}
        counts['nsf_programs_queried'] = len(nsf_programs)
        counts['nsf_awards_observed'] = len({a['id'] for p in nsf_programs.values() for a in p['awards']})
        if isinstance(http, ResumeClient):
            http.saved.clear()
        stage = 'transform'
        now = datetime.now(timezone.utc)
        records = transform(grants, awards, publications, papers, coverage, now,
                            trials=trials, nsf_programs=nsf_programs)
        counts.update(published_opportunities=len(records), excluded_or_deduped=len(grants)-len(records),
                      award_links=sum(len(r['linked_awards']) for r in records),
                      paper_links=sum(len(r['linked_papers']) for r in records),
                      trial_links=sum(len(r['linked_trials']) for r in records),
                      trial_linked_opportunities=sum(bool(r['linked_trials']) for r in records),
                      nsf_program_award_links=sum(len(r['linked_nsf_program_awards']) for r in records),
                      nsf_program_linked_opportunities=sum(bool(r['linked_nsf_program_awards']) for r in records),
                      linked_opportunities=sum(bool(r['links']) for r in records),
                      any_research_linked_opportunities=sum(bool(r['links'] or r['linked_trials']
                                                                 or r['linked_nsf_program_awards']) for r in records))
        def status(items, reused=False):
            return {'status':'ok', 'last_success_at':max(x['ref']['fetched_at'] for x in items),
                    'oldest_response_at':min(x['ref']['fetched_at'] for x in items), 'reused_weekly_cache':reused}
        statuses = {'grants_gov':status(grants), 'nih_reporter':status(awards,not refresh),
                    'openalex':status(papers,not refresh),
                    'clinical_trials_gov': {
                        'status': 'ok', 'oldest_response_at': trial_time,
                        'last_success_at': max(s['ref']['fetched_at'] for s in trials.values()),
                        'reused_weekly_cache': not trial_refresh,
                    }, **nsf_status}
        stage = 'postgres_publication'
        publish_feed(conn, records, now.isoformat(), counts, statuses, caches)
        result = health(conn)
        log.info(json.dumps({'message':'Published the updated feed','level':'info',
                             'event':'feed_build_success','feed_generated_at':now.isoformat(),
                             'per_source_counts':counts, 'research_refreshed':refresh}))
        return result
    except Exception as exc:
        # Exception class/stage only: source/DSN errors can contain credential values.
        failed_sources = {'grants_gov':['grants_gov'],
                          'nih_reporter_openalex':['nih_reporter','openalex'],
                          'clinical_trials_gov':['clinical_trials_gov'],
                          'nsf_award_search':['nsf_award_search']}.get(stage, [])
        for name in failed_sources:
            statuses[name] = {**statuses.get(name,{}), 'status':'refresh_failed'}
        error_type = type(exc).__name__
        record_failure(conn, counts, f'{stage}: {error_type}', statuses)
        log.error(json.dumps({'message':f'Feed build failed at {stage} ({error_type})','level':'error',
                              'event':'feed_build_failed','feed_generated_at':None,
                              'failed_stage':stage,'error_type':error_type,
                              'per_source_counts':counts}))
        raise SourceError(f'Feed build failed at {stage}; last good feed retained ({error_type})') from None
    finally:
        conn.execute('SELECT pg_advisory_unlock(724421702)')
