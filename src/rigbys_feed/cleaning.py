"""Conservative normalization of Grants.gov's structured synopsis fields."""
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from html import unescape
from html.parser import HTMLParser
import hashlib
import re


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []
    def handle_data(self, data):
        self.parts.append(data)


def text(value):
    value = str(value or '')
    for _ in range(3):
        decoded = unescape(value)
        if decoded == value:
            break
        value = decoded
    parser = _Text()
    parser.feed(value)
    parser.close()
    return ' '.join(unescape(' '.join(parser.parts)).split())


def deadline(synopsis):
    """Date precision only; midnight UTC is an indexing convention, not a closing hour."""
    raw = synopsis.get('responseDateStr')
    if raw:
        try:
            return date.fromisoformat(raw[:10]).isoformat() + 'T00:00:00+00:00'
        except ValueError:
            pass
    raw = synopsis.get('responseDate')
    if raw:
        for fmt in ('%m/%d/%Y', '%b %d, %Y', '%B %d, %Y', '%Y-%m-%d'):
            # Timestamp suffixes are source display formatting, not deadline-time precision.
            candidate = re.sub(r' \d{1,2}:\d{2}:\d{2}.*$', '', raw)
            try:
                return datetime.strptime(candidate, fmt).date().isoformat() + 'T00:00:00+00:00'
            except ValueError:
                continue
        raise ValueError('Unrecognized nonempty deadline; manual review required')
    return None


def amount(value):
    if value is None or str(value).strip().lower() in {'', 'none', 'n/a', 'null'}:
        return None
    try:
        number = Decimal(str(value).replace(',', '').replace('$', '').strip())
        if not number.is_finite() or number < 0:
            raise ValueError('Invalid award amount')
        return int(number) if number == number.to_integral_value() else float(number)
    except InvalidOperation:
        raise ValueError('Unrecognized award amount; manual review required') from None


def prose_dates(value):
    """Extract explicit dated requirements; never infer a year or recurrence."""
    patterns = [
        (r'\b[A-Z][a-z]+ \d{1,2},? \d{4}\b', ('%B %d, %Y','%B %d %Y','%b %d, %Y','%b %d %Y')),
        (r'\b\d{1,2} [A-Z][a-z]+ \d{4}\b', ('%d %B %Y','%d %b %Y')),
        (r'\b\d{1,2}/\d{1,2}/\d{4}\b', ('%m/%d/%Y',))]
    dates = set()
    for pattern, formats in patterns:
        for match in re.findall(pattern, value):
            for fmt in formats:
                try:
                    dates.add(datetime.strptime(match,fmt).date()); break
                except ValueError:
                    pass
    return sorted(dates)


def clean(item, as_of=None):
    raw, ref = item['record'], item['ref']
    syn = raw['synopsis']
    agency = raw.get('agencyDetails') or syn.get('agencyDetails') or {}
    source_id = str(raw['id'])
    number = text(raw['opportunityNumber']).upper()
    parsed_date = deadline(syn)
    as_of = as_of or datetime.now(timezone.utc).date()
    if parsed_date and date.fromisoformat(parsed_date[:10]) < as_of:
        return None
    if syn.get('postingDateStr') and syn['postingDateStr'][:10] > as_of.isoformat():
        return None
    source_deadline = parsed_date
    deadline_description = text(syn.get('responseDateDesc'))
    rolling = any(phrase in deadline_description.lower() for phrase in (
        'accepted anytime', 'accepted at any time', 'continuing basis', 'no submission deadline',
        'no application submission deadline', 'rolling applications', 'rolling basis',
        'open until superseded', 'submitted at any time', 'indefinite opportunity'))
    if not parsed_date:
        dates = prose_dates(deadline_description)
        if dates and max(dates) < as_of:
            return None
        if not rolling:
            if len(dates) == 1:
                parsed_date = dates[0].isoformat() + 'T00:00:00+00:00'
            else:
                # Unresolved/attachment-only dates cannot substantiate an open opportunity.
                return None
    if rolling:
        parsed_date = None
    floor, ceiling = amount(syn.get('awardFloor')), amount(syn.get('awardCeiling'))
    award = None if floor is None and ceiling is None else {
        'currency': 'USD', 'floor': floor, 'ceiling': ceiling,
        'note': 'Source-stated bounds; zero is preserved, not an estimate of expected funding.'}
    eligibility = sorted({text(x['description']) for x in syn.get('applicantTypes', [])
                          if x.get('description')})
    details = text(syn.get('applicantEligibilityDesc'))
    if details:
        eligibility.append(details)
    url = f'https://www.grants.gov/search-results-detail/{source_id}'
    base_ref = {**ref, 'source_id': source_id, 'url': url}
    paths = {
        'title_normalized': 'opportunityTitle', 'sponsor_normalized': 'agencyDetails.agencyName',
        'deadline_parsed': 'synopsis.responseDateStr / responseDate / responseDateDesc',
        'deadline_description': 'synopsis.responseDateDesc',
        'source_deadline_date': 'synopsis.responseDateStr / responseDate / responseDateDesc',
        'deadline_precision': 'synopsis.responseDateDesc / responseDate',
        'eligibility_parsed': 'synopsis.applicantTypes + applicantEligibilityDesc',
        'award_amount_parsed': 'synopsis.awardFloor + awardCeiling',
        'description': 'synopsis.synopsisDesc', 'opportunity_number': 'opportunityNumber',
        'dedupe_key': 'agencyDetails.agencyCode + opportunityNumber', 'source_ids': 'id'}
    return {
        'opportunity_id': 'gg-' + source_id,
        'dedupe_key': hashlib.sha256(f'{agency.get("agencyCode",raw.get("owningAgencyCode",""))}|{number}'.encode()).hexdigest(),
        'opportunity_number': number, 'title_normalized': text(raw['opportunityTitle']),
        'sponsor_normalized': text(agency.get('agencyName') or raw.get('owningAgencyCode')),
        'deadline_parsed': parsed_date, 'deadline_precision': 'rolling' if rolling else ('date' if parsed_date else 'unspecified'),
        'source_deadline_date': source_deadline,
        'deadline_description': deadline_description,
        'eligibility_parsed': eligibility, 'award_amount_parsed': award,
        'source_ids': [{'source': 'grants_gov', 'id': source_id}],
        'description': text(syn.get('synopsisDesc')),
        'fetched_at': ref['fetched_at'], 'updated_at': ref['fetched_at'],
        'source_refs': {k: [{**base_ref, 'field': v}] for k,v in paths.items()},
        'change_log': [],
        'quality_flags': (['eligibility_source_contains_restrictions_read_full_text']
            if 'not eligible' in details.lower() else []) + (['rolling_submission'] if rolling else (['deadline_not_specified'] if not parsed_date else [])) +
            (['source_deadline_over_ten_years_away'] if parsed_date and int(parsed_date[:4]) > as_of.year + 10 else [])}


def clean_all(items, as_of=None):
    deduped = {}
    for item in items:
        record = clean(item, as_of)
        if record is None:
            continue
        key = record['dedupe_key']
        if key in deduped:
            existing = deduped[key]
            existing['source_ids'] = sorted(existing['source_ids'] + record['source_ids'], key=lambda x:x['id'])
            # Keep the newest fetched source if duplicate opportunity numbers exist.
            if record['fetched_at'] > existing['fetched_at']:
                record['source_ids'] = existing['source_ids']
                deduped[key] = record
        else:
            deduped[key] = record
    return sorted(deduped.values(), key=lambda x:x['opportunity_id'])
