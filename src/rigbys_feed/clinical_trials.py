"""ClinicalTrials.gov records joined by explicit study or NIH award IDs."""
from collections import defaultdict
import re

from .research import chunks
from .sources import SourceError

SOURCE = 'clinical_trials_gov'
NCT = re.compile(r'\bNCT\d{8}\b', re.IGNORECASE | re.ASCII)
NIH_CORE = re.compile(r'(?:[1-9])?([A-Z][A-Z0-9]{2}[A-Z]{2}[0-9]{6})(?:-[0-9]{2}(?:[AS][0-9]+)*)?')


def nih_core(value):
    match = NIH_CORE.fullmatch(re.sub(r'\s+', '', value.upper()))
    return match[1] if match else None


def mentioned_ids(record):
    return {match.group().upper() for text in (
        record['opportunityTitle'], record['synopsis'].get('synopsisDesc') or '',
    ) for match in NCT.finditer(text)}


class ClinicalTrials:
    url = 'https://clinicaltrials.gov/api/v2/studies'

    def __init__(self, http):
        self.http = http

    def _studies(self, filters):
        params = {**filters, 'pageSize': 1000, 'countTotal': 'true',
                  'fields': 'NCTId,BriefTitle,SecondaryIdInfo,OverallStatus'}
        records, pages = {}, set()
        expected, oldest = None, None
        while True:
            data, ref = self.http.request(SOURCE, 'GET', self.url, params=dict(params))
            rows, total = data.get('studies'), data.get('totalCount', expected)
            if not isinstance(rows, list) or type(total) is not int or total < 0:
                raise SourceError(f'{SOURCE}: invalid study page')
            if expected is not None and expected != total:
                raise SourceError(f'{SOURCE}: study count changed during pagination')
            expected = total
            oldest = min(oldest, ref['fetched_at']) if oldest else ref['fetched_at']
            for row in rows:
                protocol = row.get('protocolSection', {})
                identity = protocol.get('identificationModule', {})
                nct = identity.get('nctId', '')
                if not NCT.fullmatch(nct) or nct != nct.upper() or nct in records:
                    raise SourceError(f'{SOURCE}: invalid or repeated study ID')
                records[nct] = {
                    'nct_id': nct, 'title': identity.get('briefTitle'),
                    'status': protocol.get('statusModule', {}).get('overallStatus'),
                    'nih_ids': {item['id']: core
                                for item in identity.get('secondaryIdInfos', [])
                                if item.get('type') == 'NIH' and isinstance(item.get('id'), str)
                                and (core := nih_core(item['id']))},
                    'ref': ref,
                }
            token = data.get('nextPageToken')
            if not token:
                if len(records) != expected:
                    raise SourceError(f'{SOURCE}: incomplete study pages')
                return records, oldest
            if not rows or not isinstance(token, str) or token in pages or len(records) >= expected:
                raise SourceError(f'{SOURCE}: invalid study pagination')
            pages.add(token)
            params['pageToken'] = token

    def nih_studies(self):
        records, stamp = self._studies({'filter.advanced': 'AREA[SecondaryIdType]NIH'})
        if not records:
            raise SourceError(f'{SOURCE}: empty NIH-identified study collection')
        return records, stamp

    def studies_by_id(self, nct_ids):
        records = {}
        for group in chunks(nct_ids, 100):
            result, _ = self._studies({'filter.ids': ','.join(group)})
            if not result.keys() <= set(group):
                raise SourceError(f'{SOURCE}: study ID filter not honored')
            records.update(result)
        return records


def attach_trials(records, studies):
    by_core = defaultdict(list)
    for study in studies.values():
        for raw_id, core in study['nih_ids'].items():
            by_core[core].append((study, raw_id))
    for record in records:
        linked = {}
        opportunity_id = record['opportunity_id']

        def add(study, relationship, confidence, evidence):
            nct = study['nct_id']
            if nct in linked:
                return
            linked[nct] = dict(opportunity_id=opportunity_id, link_type='trial', target_id=nct,
                               target_url=f'https://clinicaltrials.gov/study/{nct}',
                               title=study['title'], status=study['status'],
                               join_confidence=confidence, relationship=relationship,
                               evidence={**evidence, 'registry_ref': study['ref']})

        for field in ('title_normalized', 'description'):
            for match in NCT.finditer(record[field]):
                if study := studies.get(match.group().upper()):
                    add(study, 'study_id_cited_in_opportunity', 1.0,
                        {'cited_id': match.group(), 'opportunity_refs': record['source_refs'][field]})
        for award in record['linked_awards']:
            core = award['evidence'].get('core_project_num')
            if not core or not NIH_CORE.fullmatch(core):
                continue
            for study, raw_id in by_core[core]:
                add(study, 'study_registry_reports_linked_nih_award', 0.95,
                    {'via_award': award['target_id'], 'award_url': award['target_url'],
                     'core_project_num': core, 'registry_nih_id': raw_id})
        record['linked_trials'] = [linked[key] for key in sorted(linked)]
        record['source_refs']['linked_trials'] = [{
            'source': SOURCE, 'evidence_field': 'linked_trials[].evidence',
            'note': 'Registry-confirmed links provide context and are excluded from scoring.'}]
        record['source_ids'].extend({'source': SOURCE, 'id': key} for key in sorted(linked))
