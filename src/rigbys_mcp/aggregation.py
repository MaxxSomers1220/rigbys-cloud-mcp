"""Source-backed portfolio aggregation over rows already matched by PostgreSQL.

This module performs no upstream reads and does not approximate the database's
English full-text matching. Year intervals bound counts without inventing dates.
"""
from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, timezone
import math
from statistics import median

SCORES = ('growth_score','momentum_score','novelty_score','gap_score')
WINDOW_PRECISION = ('source-year intervals overlap the requested calendar window; '
                    'not exact award/publication dates')
GROUPING_METHOD = 'normalized opportunity-title groups; not scientific taxonomy'


def _as_date(value):
    if value is None:
        return datetime.now(timezone.utc).date()
    if isinstance(value,datetime):
        return value.date()
    if isinstance(value,date):
        return value
    if isinstance(value,str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    raise ValueError('as_of must be an ISO date')


def _cutoff(as_of, months):
    year, month = divmod(as_of.year*12+as_of.month-1-months,12)
    month += 1
    return date(year,month,min(as_of.day,monthrange(year,month)[1]))


def _year_interval(year, fiscal):
    if type(year) is not int or not 2<=year<=9998:
        return None
    return (date(year-1,10,1),date(year,9,30)) if fiscal else (date(year,1,1),date(year,12,31))


def _source_counts(rows, cutoff, as_of):
    awards, papers, unknown_awards, unknown_papers, known_awards, known_papers = [set() for _ in range(6)]
    opportunities = {'grants_gov':set(), 'aha':set()}
    for row in rows:
        identifier=row.get('opportunity_id')
        if isinstance(identifier,str):
            if identifier.startswith('gg-'):
                opportunities['grants_gov'].add(identifier)
            elif identifier.startswith('aha-'):
                opportunities['aha'].add(identifier)
        for field, year_field, fiscal, eligible, unknown, known in (
            ('linked_awards','fiscal_year',True,awards,unknown_awards,known_awards),
            ('linked_papers','publication_year',False,papers,unknown_papers,known_papers)):
            for link in row.get(field) or []:
                identifier=link.get('target_id')
                if not identifier:
                    continue
                interval=_year_interval(link.get(year_field),fiscal)
                if interval is None:
                    unknown.add(identifier)
                else:
                    known.add(identifier)
                    if interval[0]<=as_of and interval[1]>=cutoff:
                        eligible.add(identifier)
    counts={'grants_gov':len(opportunities['grants_gov']),
            'nih_reporter':len(awards),'openalex':len(papers)}
    # Preserve the federal-only response shape. Research edge/source-reference
    # identifiers never become additional opportunities or AHA program counts.
    if opportunities['aha']:
        counts['aha']=len(opportunities['aha'])
    return counts, {
        'award_period_unknown_count':len(unknown_awards-known_awards),
        'paper_period_unknown_count':len(unknown_papers-known_papers)}


def _status(row):
    evidence=row.get('score_evidence')
    return evidence.get('status') if isinstance(evidence,dict) else None


def _observed(row):
    return _status(row)=='descriptive_proxy' and all(
        type(row.get(field)) in (int,float) and math.isfinite(row[field]) and 0<=row[field]<=100
        for field in SCORES)


def _medians(rows, comparable):
    return {'median_'+field:median([row[field] for row in rows]) if comparable and rows else None
            for field in SCORES}


def _iso(value):
    return value.isoformat() if isinstance(value,(date,datetime)) else value


def _citations(rows):
    citations={}
    for row in rows:
        for ref in (row.get('source_refs') or {}).get('title_normalized',[]) or []:
            if not isinstance(ref,dict) or not ref.get('url'):
                continue
            key=(row['opportunity_id'],ref['url'])
            citations[key]={'opportunity_id':row['opportunity_id'],
                            'title_normalized':row['title_normalized'],'source_url':ref['url'],
                            'feed_generated_at':_iso(row.get('feed_generated_at')),
                            'fetched_at':_iso(ref.get('fetched_at'))}
    return [citations[key] for key in sorted(citations)]


def aggregate(rows, topic, window_months=12, as_of=None):
    """Aggregate topic-matched source projections; return no confident gap claims.

    Only descriptive_proxy records with all valid numeric scores enter medians
    and rankings. Neutral insufficient-data placeholders remain in counts and
    are disclosed. Mixed or missing methodology versions suppress comparisons.
    """
    if not isinstance(topic,str) or not topic.strip() or len(topic)>500:
        raise ValueError('Topic must be a nonempty string of at most 500 characters')
    if type(window_months) is not int or not 1<=window_months<=120:
        raise ValueError('window_months must be an integer from 1 to 120')
    as_of=_as_date(as_of)
    try:
        cutoff=_cutoff(as_of,window_months)
    except (ValueError,OverflowError):
        raise ValueError('Requested calendar window is outside supported dates') from None
    by_id={}
    for row in rows:
        if not row.get('opportunity_id'):
            raise ValueError('Aggregate source row is missing opportunity_id')
        if not isinstance(row['opportunity_id'],str) or not row['opportunity_id'].startswith(('gg-','aha-')):
            raise ValueError('Aggregate source row has an unsupported opportunity_id namespace')
        by_id.setdefault(row['opportunity_id'],row)
    rows=list(by_id.values())
    versions=sorted({row['methodology_version'] for row in rows
                     if isinstance(row.get('methodology_version'),str) and row['methodology_version']})
    missing_versions=any(not isinstance(row.get('methodology_version'),str) or not row['methodology_version']
                         for row in rows)
    comparable=len(versions)==1 and not missing_versions
    version=versions[0] if comparable else None
    observed=[row for row in rows if _observed(row)]
    neutral_count=sum(_status(row)=='insufficient_data_neutral_placeholder'
                      for row in rows)
    counts, unknown_periods=_source_counts(rows,cutoff,as_of)
    thin=len(observed)<5 or counts['nih_reporter']<5 or counts['openalex']<10
    if not rows:
        status='no_matching_opportunities'
    elif len(versions)>1:
        status='mixed_methodologies'
    elif missing_versions:
        status='methodology_unavailable'
    elif not observed:
        status='insufficient_data'
    elif thin:
        status='thin_sample'
    else:
        status='descriptive_proxy'
    groups=defaultdict(list)
    for row in rows:
        title=' '.join(str(row.get('title_normalized') or '').split())
        if title:
            groups[title].append(row)
    summaries=[]
    for title, members in sorted(groups.items()):
        measured=[row for row in members if _observed(row)]
        group_counts, group_unknown=_source_counts(members,cutoff,as_of)
        group_thin=len(measured)<5 or group_counts['nih_reporter']<5 or group_counts['openalex']<10
        summaries.append({'subtopic':title,'opportunity_ids':sorted(row['opportunity_id'] for row in members),
                          'open_opportunity_count':len(members),
                          'awarded_grant_count':group_counts['nih_reporter'],'paper_count':group_counts['openalex'],
                          'source_counts':group_counts, **group_unknown,
                          'scored_opportunity_count':len(measured),
                          'insufficient_data_count':len(members)-len(measured),
                          'methodology_version':version, **_medians(measured,comparable),
                          'score_status':('thin_sample' if group_thin else 'descriptive_proxy') if measured and comparable else 'insufficient_or_incomparable_data',
                          'thin_sample':group_thin,
                          'source_refs':_citations(members)})
    ranked=[group for group in summaries if group['median_gap_score'] is not None]
    neglected=sorted(ranked,key=lambda group:(-group['median_gap_score'],group['subtopic'].casefold(),group['subtopic']))[:5]
    crowded=sorted(ranked,key=lambda group:(group['median_gap_score'],group['subtopic'].casefold(),group['subtopic']))[:5]
    feed_times=[_iso(row.get('feed_generated_at')) for row in rows if row.get('feed_generated_at')]
    return {
        'topic':topic.strip(),'window_months':window_months,'window_start':cutoff.isoformat(),
        'as_of':as_of.isoformat(),'window_precision':WINDOW_PRECISION,
        'opportunity_count_basis':'open_in_last_successful_feed',
        'open_opportunity_count':len(rows),'awarded_grant_count':counts['nih_reporter'],
        'paper_count':counts['openalex'],'source_counts':counts, **unknown_periods,
        'methodology_version':version,'methodology_versions':versions,
        'scored_opportunity_count':len(observed),'insufficient_data_count':len(rows)-len(observed),
        'neutral_placeholder_count':neutral_count,'neutral_placeholder_value':50,
        'neutral_placeholder_status':'insufficient_data_neutral_placeholder',
        **_medians(observed,comparable), 'grouping_method':GROUPING_METHOD,
        'top_neglected_subtopics':neglected,'top_crowded_subtopics':crowded,
        'sample_status':status,'thin_sample':thin,'feed_generated_at':max(feed_times) if feed_times else None,
        'notice':('Open-opportunity counts describe the last successful feed, not live source status. Research counts are distinct source identifiers within overlapping fiscal/calendar-year intervals, '
                  'not exact award or publication dates. Scores remain their original versioned portfolio proxies; '
                  'they are not recalculated for the requested window. Neutral 50 placeholders are excluded from '
                  'medians and rankings. A thin sample cannot establish a confident funding gap. Mixed or missing '
                  'methodologies suppress comparative scores and rankings. Opportunity-title groups are not a '
                  'scientific taxonomy. High gap proxies are not proof of neglect or underfunding; broad FOA and '
                  'award-core publication associations do not prove current-opportunity funding or topic relevance.')}
