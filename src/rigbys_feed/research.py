"""Exact-identifier research retrieval; complete within a declared fiscal-year window.

RePORTER award coverage is the current federal fiscal year and three previous
fiscal years by default. OpenAlex coverage is indexed works explicitly naming
those awards in public funding metadata. RePORTER publication lookup is retained
for corroboration, with source caps enforced. No title-based matches are used.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import logging
import re

from .sources import SourceError, utcnow

log = logging.getLogger(__name__)


def chunks(items, size):
    items = sorted(set(str(item).strip() for item in items if item is not None and str(item).strip()))
    for start in range(0, len(items), size):
        yield items[start:start + size]


def default_fiscal_years():
    now = datetime.now(timezone.utc)
    current = now.year + (now.month >= 10)
    return list(range(current - 3, current + 1))


class Reporter:
    base = 'https://api.reporter.nih.gov/v2/'

    def __init__(self, http):
        self.http = http

    def _query(self, endpoint, field, identifiers, extra=None):
        """Partition before endpoint row caps (awards 15k; publications 10k)."""
        if not identifiers:
            return []
        offset, results, seen_pages, seen_rows = 0, [], set(), set()
        expected_total = None
        while True:
            payload = {'criteria': {field: identifiers, **(extra or {})}, 'offset': offset, 'limit': 500}
            if endpoint == 'publications/search':
                payload.update(sort_field='pmid', sort_order='asc')
            response, ref = self.http.request('nih_reporter', 'POST', self.base + endpoint, json=payload)
            if not isinstance(response.get('results'), list) or not isinstance(response.get('meta', {}).get('total'), int):
                raise SourceError('nih_reporter: malformed paginated response')
            total, page = response['meta']['total'], response['results']
            if response['meta'].get('offset', offset) != offset:
                raise SourceError('nih_reporter: requested offset not honored')
            if expected_total is not None and total != expected_total:
                raise SourceError('nih_reporter: total changed during pagination; retry snapshot')
            expected_total = total
            fingerprint = json.dumps(page, sort_keys=True)
            if page and fingerprint in seen_pages:
                raise SourceError('nih_reporter: repeated pagination page')
            seen_pages.add(fingerprint)
            row_keys = [json.dumps(row, sort_keys=True) for row in page]
            if any(key in seen_rows for key in row_keys):
                if len(identifiers) > 1:
                    middle = len(identifiers) // 2
                    return (self._query(endpoint, field, identifiers[:middle], extra) +
                            self._query(endpoint, field, identifiers[middle:], extra))
                raise SourceError('nih_reporter: overlapping pagination rows')
            seen_rows.update(row_keys)
            cap = 9999 if endpoint == 'publications/search' else 14999
            if total > cap:
                if len(identifiers) == 1:
                    raise SourceError('nih_reporter: single identifier exceeds pagination cap; narrow fiscal-year coverage')
                middle = len(identifiers) // 2
                return (self._query(endpoint, field, identifiers[:middle], extra) +
                        self._query(endpoint, field, identifiers[middle:], extra))
            if not page and offset < total:
                raise SourceError('nih_reporter: incomplete pagination')
            results.extend({'record': row, 'ref': dict(ref)} for row in page)
            offset += len(page)
            if offset >= total:
                return results

    def awards(self, foas, fiscal_years=None):
        years = default_fiscal_years() if fiscal_years is None else sorted(set(fiscal_years))
        if not years:
            raise ValueError('at least one fiscal year is required')
        records = {}
        jobs = [(group, year) for group in chunks(foas, 100) for year in years]
        def fetch_job(job):
            group, year = job
            return group, year, self._query('projects/search', 'foa', group, {'fiscal_years': [year]})
        with ThreadPoolExecutor(max_workers=3) as pool:
            for group, year, rows in pool.map(fetch_job, jobs):
                for wrapped in rows:
                    row = wrapped['record']
                    if str(row.get('opportunity_number', '')).upper() not in {f.upper() for f in group}:
                        raise SourceError('nih_reporter: FOA filter not honored')
                    if row.get('fiscal_year') != year or row.get('appl_id') is None or not row.get('core_project_num'):
                        raise SourceError('nih_reporter: award identifiers or fiscal-year scope missing')
                    identity = (row['appl_id'], row.get('subproject_id'))
                    records[identity] = wrapped
        result = list(records.values())
        log.info(json.dumps({'source': 'nih_reporter_awards', 'count': len(result), 'fiscal_years': years, 'fetched_at': utcnow()}))
        return result

    def publications(self, core_project_nums):
        records = {}
        def fetch_group(group):
            return group, self._query('publications/search', 'core_project_nums', group)
        with ThreadPoolExecutor(max_workers=3) as pool:
            for group, rows in pool.map(fetch_group, chunks(core_project_nums, 100)):
                for wrapped in rows:
                    row = wrapped['record']
                    if row.get('coreproject') not in group or not row.get('pmid'):
                        raise SourceError('nih_reporter: publication identifiers or core-project filter missing')
                    records[(row['coreproject'], str(row['pmid']))] = wrapped
        result = list(records.values())
        log.info(json.dumps({'source': 'nih_reporter_publications', 'count': len(result), 'fetched_at': utcnow()}))
        return result


class OpenAlex:
    base = 'https://api.openalex.org/works'

    def __init__(self, http):
        self.http = http

    def papers(self, pmids):
        groups = list(chunks(pmids, 100))
        if len(groups) > 1:
            with ThreadPoolExecutor(max_workers=3) as pool:
                return [row for result in pool.map(self.papers, groups) for row in result]
        records = {}
        for group in chunks(pmids, 100):
            cursor, cursors = '*', set()
            count, seen = None, set()
            while cursor:
                if cursor in cursors:
                    raise SourceError('openalex: repeated pagination cursor')
                cursors.add(cursor)
                response, ref = self.http.request('openalex', 'GET', self.base,
                    params={'filter': 'pmid:' + '|'.join(group), 'per-page': 100, 'cursor': cursor})
                meta, page = response.get('meta', {}), response.get('results')
                if not isinstance(page, list) or not isinstance(meta.get('count'), int):
                    raise SourceError('openalex: malformed paginated response')
                count = meta['count'] if count is None else count
                for row in page:
                    if not row.get('id') or not row.get('ids', {}).get('pmid'):
                        raise SourceError('openalex: paper identifiers missing')
                    pmid = str(row['ids']['pmid']).rstrip('/').rsplit('/', 1)[-1]
                    if pmid not in group:
                        raise SourceError('openalex: PMID filter not honored')
                    records[row['id']] = {'record': row, 'ref': dict(ref)}
                    seen.add(row['id'])
                cursor = meta.get('next_cursor')
                if not cursor and len(seen) < count:
                    raise SourceError('openalex: incomplete pagination')
                if cursor and not page:
                    raise SourceError('openalex: empty pagination page')
        result = list(records.values())
        log.info(json.dumps({'source': 'openalex', 'count': len(result), 'fetched_at': utcnow()}))
        return result


    def papers_for_awards(self, core_project_nums):
        """Works whose public funding metadata explicitly names a scoped award.

        This route avoids RePORTER's 10,000-publication cap for long-running
        centers. It is an OpenAlex-indexed funding-metadata corpus, not a claim
        to contain every publication ever associated with an NIH award.
        """
        records = {}
        groups = list(chunks(core_project_nums, 100))
        with ThreadPoolExecutor(max_workers=3) as pool:
            for rows in pool.map(self._award_papers_group, groups):
                for row in rows:
                    records[row['record']['id']] = row
        result = list(records.values())
        log.info(json.dumps({'source': 'openalex', 'count': len(result), 'linkage': 'exact_award_funding_metadata', 'fetched_at': utcnow()}))
        return result

    def _award_papers_group(self, group, year_filter=None, year_bounds=None):
        # OpenAlex permits public basic paging through 10,000 rows. Cursor
        # paging now requires a key, so partition queries before that boundary.
        page_number, records, expected = 1, {}, None
        while True:
            source_filter = 'awards.funder_award_id:' + '|'.join(group)
            if year_filter:
                source_filter += ',' + year_filter
            response, ref = self.http.request('openalex', 'GET', self.base,
                params={'filter': source_filter, 'per-page': 200, 'page': page_number,
                        'select': 'id,ids,title,publication_year,publication_date,awards,topics,counts_by_year,cited_by_count'})
            meta, page = response.get('meta', {}), response.get('results')
            if not isinstance(page, list) or not isinstance(meta.get('count'), int):
                raise SourceError('openalex: malformed paginated response')
            if expected is not None and meta['count'] != expected:
                raise SourceError('openalex: total changed during pagination; retry snapshot')
            expected = meta['count']
            if expected > 10000:
                if len(group) > 1:
                    middle = len(group) // 2
                    children = (self._award_papers_group(group[:middle], year_filter, year_bounds) +
                                self._award_papers_group(group[middle:], year_filter, year_bounds))
                    # Shared funding can put one paper into several award groups.
                    unique = {row['record']['id']: row for row in children}
                else:
                    lower, upper = year_bounds or (0, datetime.now(timezone.utc).year + 2)
                    if upper - lower <= 1:
                        raise SourceError('openalex: single award/year exceeds public pagination cap')
                    middle = (lower + upper) // 2
                    if year_bounds is None:
                        filters = (f'publication_year:<{middle}', f'publication_year:>{middle-1}')
                    else:
                        filters = (f'publication_year:{lower}-{middle-1}', f'publication_year:{middle}-{upper-1}')
                    children = (self._award_papers_group(group, filters[0], (lower, middle)) +
                                self._award_papers_group(group, filters[1], (middle, upper)))
                    unique = {row['record']['id']: row for row in children}
                if len(unique) != expected:
                    raise SourceError('openalex: partitioned query counts do not match source total')
                return list(unique.values())
            for row in page:
                funded_cores = {str(a.get('funder_award_id', '')).upper() for a in row.get('awards', [])}
                if not row.get('id') or not funded_cores.intersection(group):
                    raise SourceError('openalex: award filter not supported by exact funding metadata')
                if row['id'] in records:
                    raise SourceError('openalex: overlapping pagination rows')
                records[row['id']] = {'record': row, 'ref': dict(ref)}
            if len(records) >= expected:
                if len(records) != expected:
                    raise SourceError('openalex: pagination exceeded source total')
                return list(records.values())
            if not page:
                raise SourceError('openalex: incomplete pagination')
            page_number += 1


def fetch_research(http, grants, fiscal_years=None):
    years = default_fiscal_years() if fiscal_years is None else list(fiscal_years)
    # Generic federal numbers are substring matched by NIH and can retrieve
    # unrelated awards. Restrict research queries to standard NIH FOA numbers.
    foas = [g['record']['opportunityNumber'].upper() for g in grants
            if re.fullmatch(r'(?:PA|PAR|PAS|RFA)-\d{2}-\d{3}', g['record']['opportunityNumber'].upper())]
    reporter = Reporter(http)
    awards = reporter.awards(foas, years)
    publications = []
    papers = OpenAlex(http).papers_for_awards([a['record']['core_project_num'] for a in awards])
    coverage = {
        'fiscal_years': years, 'opportunity_foas_queried': len(set(foas)),
        'award_count': len(awards), 'publication_links': 0,
        'openalex_papers': len(papers),
        'award_scope': 'Exact NIH opportunity numbers; current and previous three federal fiscal years by default.',
        'publication_scope': 'Bulk RePORTER publications not requested: source caps single-core results at 10,000; available separately for sample corroboration.',
        'paper_scope': 'OpenAlex-indexed works explicitly naming a scoped NIH core project in awards.funder_award_id; no inferred matches.',
        'missing_metadata': 'Works without exact indexed funding metadata are not linked; absence is not evidence of no research.',
    }
    return awards, publications, papers, coverage
