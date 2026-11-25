"""Reviewed-subset AHA source verification; no discovery, SQL or publication.

An explicit manifest opts into fresh ordinary public GETs. An incomplete review or
any required-source failure raises instead of returning partial/empty success.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from importlib.resources import files
from io import BytesIO
import hashlib
import json
from pathlib import Path
import re
import time
import unicodedata
from urllib.parse import urljoin, urlsplit
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
from pypdf import PdfReader

from .cleaning import amount, text
from .sources import SourceError

MAX_BYTES = 10 * 1024 * 1024
MAX_ATTEMPTS = 5
GENERAL_URL = 'https://professional.heart.org/en/research-programs/application-resources'
GENERAL_ASSERTIONS = frozenset({'general_application_identity','membership','immigration_status','institutional_authorization'})
TIMEOUT = 90
STATES = tuple('AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY'.split())
CENTRAL = ZoneInfo('America/Chicago')
ALLOWED_URLS = frozenset({
    'https://professional.heart.org/en/research-programs/application-resources',
    'https://professional.heart.org/en/research-programs/aha-funding-opportunities/career-development-award',
    'https://professional.heart.org/en/research-programs/aha-funding-opportunities/innovative-project-award',
    'https://professional.heart.org/en/-/media/PHD-Files/Research/Funding-Opportunities-Media-Folder/Career-Development-Award.pdf?sc_lang=en',
    'https://professional.heart.org/en/-/media/PHD-Files/Research/Funding-Opportunities-Media-Folder/Innovative-Project-Award.pdf?sc_lang=en',
})
PROGRAMS = frozenset({'career-development-award', 'innovative-project-award'})
PROGRAM_DOCUMENTS = {
    'career-development-award': ('aha_career_rfp', 'Career-Development-Award'),
    'innovative-project-award': ('aha_innovative_rfp', 'Innovative-Project-Award'),
}


@dataclass
class AhaBatch:
    records: list = field(default_factory=list)
    scope: dict = field(default_factory=dict)
    references: list = field(default_factory=list)
    verification: dict = field(default_factory=dict)
    counts: dict = field(default_factory=dict)

    @property
    def refs(self):
        return self.references


class AhaVerificationError(SourceError):
    def __init__(self, reason, *, references=(), verification=None):
        super().__init__('aha: ' + reason)
        self.references = list(references)
        self.refs = self.references
        self.verification = {'status': 'failed', **(verification or {})}


def default_manifest_path():
    development = Path(__file__).resolve().parents[2] / 'config/sources/aha-reviewed.json'
    return development if development.is_file() else Path(str(files('rigbys_feed').joinpath('config/sources/aha-reviewed.json')))


def resolve_manifest_path(path=None):
    return Path(path) if path is not None else default_manifest_path()


def _aware(instant):
    if not isinstance(instant, datetime) or instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError('Timezone-aware instant required')
    return instant


def _stamp():
    return datetime.now(timezone.utc).isoformat()


def _approved(url):
    parsed = urlsplit(url)
    return (url in ALLOWED_URLS and parsed.scheme == 'https' and parsed.hostname == 'professional.heart.org'
            and parsed.port is None and not parsed.username and not parsed.password and not parsed.fragment)


def review_binding(manifest):
    """A review must deliberately bind facts/assertions to exact original bytes.

    Not an authentication signature: the manifest is an operator-reviewed input.
    Editing material facts requires a new explicit review digest, never an
    automatic newest-wins replacement of the approved source version.
    """
    value={k:v for k,v in manifest.items() if k not in {'review_binding_sha256','activation_note','_sha256'}}
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def load_manifest(path):
    path = Path(path)
    try:
        raw = path.read_bytes()
        manifest = json.loads(raw)
        if not isinstance(manifest, dict) or manifest.get('schema_version') != 1 or manifest.get('provider') != 'aha':
            raise ValueError('schema/provider')
        cycle = str(manifest['cycle'])
        if not re.fullmatch(r'20\d{2}', cycle):
            raise ValueError('cycle')
        programs = manifest['programs']
        keys = [p['key'] for p in programs]
        if len(keys) != len(set(keys)) or set(keys) != PROGRAMS:
            raise ValueError('reviewed program identity')
        docs = manifest['documents']
        if len({d['key'] for d in docs}) != len(docs):
            raise ValueError('duplicate document identity')
        by_key = {d['key']: d for d in docs}
        if set(by_key) != {'aha_career_rfp', 'aha_innovative_rfp', 'aha_general_requirements'}:
            raise ValueError('reviewed document scope')
        for d in docs:
            if not _approved(d['url']) or d.get('format') not in {'pdf', 'html'}:
                raise ValueError('unapproved document')
            if any(not _approved(u) for u in d.get('approved_redirects', [])):
                raise ValueError('unapproved redirect')
            if d.get('review_status') == 'verified' and not re.fullmatch(r'[0-9a-f]{64}', d.get('expected_sha256') or ''):
                raise ValueError('document byte identity')
        prerequisite = manifest['general_requirements_document']
        if prerequisite != 'aha_general_requirements' or prerequisite not in by_key:
            raise ValueError('missing general prerequisite')
        general=by_key[prerequisite]
        if general['url']!=GENERAL_URL or general['format']!='html' or not GENERAL_ASSERTIONS <= {c.get('key') for c in general.get('assertions',[])}:
            raise ValueError('unverified general requirements identity/coverage')
        if manifest.get('review_binding_sha256') != review_binding(manifest):
            raise ValueError('review binding changed')
        for p in programs:
            if p['document'] not in by_key or not _approved(p['source_url']):
                raise ValueError('program document')
            document_key, filename = PROGRAM_DOCUMENTS[p['key']]
            document = by_key[p['document']]
            expected_pdf = ('https://professional.heart.org/en/-/media/PHD-Files/Research/'
                            'Funding-Opportunities-Media-Folder/' + filename + '.pdf?sc_lang=en')
            if (p['document'] != document_key or document['url'] != expected_pdf or document['format'] != 'pdf'
                    or p['source_url'] != 'https://professional.heart.org/en/research-programs/aha-funding-opportunities/' + p['key']
                    or p['expected_content_sha256'] != document.get('expected_sha256')):
                raise ValueError('program source identity/hash binding')
            if p['deadline_stage'] != {'career-development-award':'full_application','innovative-project-award':'pre_proposal'}[p['key']]:
                raise ValueError('required initial stage')
            date.fromisoformat(p['opens_date']); date.fromisoformat(p['deadline_date'])
            if date.fromisoformat(p['opens_date']) > date.fromisoformat(p['deadline_date']):
                raise ValueError('opening after deadline')
            if p['deadline_time'] != '15:00:00' or p.get('deadline_timezone', 'America/Chicago') != 'America/Chicago':
                raise ValueError('unreviewed submission time')
            if (amount(p['total_usd']) is None or p['months'] <= 0 or not isinstance(p['eligibility'],list)
                    or not p['eligibility'] or not all(isinstance(e,str) and e for e in p['eligibility'])
                    or not {'title_normalized','application_stages','eligibility_parsed','award_amount_parsed','award_period_months','description'} <= set(p['locators'])
                    or not all(isinstance(v,str) and v for v in p['locators'].values())):
                raise ValueError('material terms missing')
            if p['deadline_stage'] == 'pre_proposal':
                if not p.get('invited_full_deadline_date') or not p.get('invitation_date'):
                    raise ValueError('unknown invited gate')
                if not p['deadline_date'] < p['invitation_date'] < p['invited_full_deadline_date']:
                    raise ValueError('contradictory stage dates')
            elif p.get('invited_full_deadline_date') or p.get('invitation_date'):
                raise ValueError('unreviewed later application gate')
        manifest['_sha256'] = hashlib.sha256(raw).hexdigest()
        return manifest
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError):
        raise AhaVerificationError('invalid reviewed manifest; review required') from None


def _local_deadline(day, clock='15:00:00'):
    return datetime.fromisoformat(day + 'T' + clock).replace(tzinfo=CENTRAL)


def open_to_new_applicants(record, now):
    now = _aware(now)
    stages = record.get('application_stages') or []
    if not stages or not stages[0].get('required') or stages[0].get('invitation_required'):
        raise AhaVerificationError('unknown initial application gate')
    gate = stages[0]
    opens = date.fromisoformat(gate['opens_date'])
    deadline = datetime.fromisoformat(gate['deadline_at'])
    _aware(deadline)
    return opens <= now.astimezone(CENTRAL).date() and now < deadline


def geographic_screen(record, state):
    geo = record.get('eligibility_geography') or {}
    return (state in STATES and geo.get('country') == 'US' and geo.get('scope') == 'nationwide'
            and not geo.get('state_restrictions'))


def _archive(raw_dir, run, key, attempt, request_url, response_url, status, content_type, content, truncated):
    folder = Path(raw_dir) / 'nonfederal_documents' / 'aha' / run / key
    folder.mkdir(parents=True, exist_ok=True)
    stamp = _stamp(); digest = hashlib.sha256(content).hexdigest()
    document = folder / f'{attempt}-{digest}.bin'
    document.write_bytes(content)
    envelope = {'source': 'aha', 'url': request_url, 'final_url': response_url, 'method': 'GET',
                'fetched_at': stamp, 'status_code': status, 'content_type': content_type,
                'content_sha256': digest, 'byte_count': len(content), 'truncated': truncated,
                'document_path': str(document)}
    data = json.dumps(envelope, sort_keys=True).encode()
    metadata = folder / f'{attempt}-{hashlib.sha256(data).hexdigest()}.json'
    metadata.write_bytes(data)
    return {**{k: envelope[k] for k in ('source','url','final_url','fetched_at','content_sha256','content_type','byte_count','status_code','truncated')},
            'raw_path': str(metadata), 'sha256': hashlib.sha256(data).hexdigest()}


def _fetch(document, raw_dir, run, client, references):
    url = document['url']; redirects = 0
    for attempt in range(MAX_ATTEMPTS):
        try:
            request = httpx.Request('GET', url, headers={'Accept': 'application/pdf' if document['format'] == 'pdf' else 'text/html','Accept-Encoding':'identity'},
                                   extensions={'timeout': {k: TIMEOUT for k in ('connect','read','write','pool')}})
            response = client.send(request, auth=None, follow_redirects=False, stream=True)
            try:
                chunks=[]; size=0; truncated=False
                for chunk in response.iter_bytes():
                    remaining=MAX_BYTES+1-size
                    chunks.append(chunk[:remaining]);size+=len(chunks[-1])
                    if size>MAX_BYTES:
                        truncated=True;break
                content=b''.join(chunks)
                ref=_archive(raw_dir,run,document['key'],f'{attempt}-{redirects}',url,str(response.url),response.status_code,
                             response.headers.get('content-type','').split(';')[0].strip().lower(),content,truncated)
                references.append(ref)
                if truncated:
                    raise AhaVerificationError('document exceeds bounded byte limit',references=references)
                if response.status_code in {301,302,303,307,308}:
                    target=urljoin(url,response.headers.get('location',''))
                    if target not in document.get('approved_redirects',[]) or not _approved(target) or redirects>=3:
                        raise AhaVerificationError('unapproved document redirect',references=references)
                    redirects+=1;url=target
                    continue
                if response.status_code==429 or 500<=response.status_code<=599:
                    if attempt==MAX_ATTEMPTS-1:
                        raise AhaVerificationError('public source retries exhausted',references=references)
                    try:delay=float(response.headers.get('retry-after',2**attempt))
                    except ValueError:delay=2**attempt
                    time.sleep(min(16,max(0,delay)));continue
                if response.status_code!=200:
                    raise AhaVerificationError('public source HTTP '+str(response.status_code),references=references)
                declared=response.headers.get('content-length')
                if declared and response.headers.get('content-encoding','identity').lower()=='identity' and (not declared.isdigit() or int(declared)!=len(content)):
                    raise AhaVerificationError('truncated or inconsistent document length',references=references)
                expected_type='application/pdf' if document['format']=='pdf' else 'text/html'
                if ref['content_type']!=expected_type or not content or (document['format']=='pdf' and not content.startswith(b'%PDF-')):
                    raise AhaVerificationError('unexpected document MIME or body',references=references)
                if hashlib.sha256(content).hexdigest()!=document['expected_sha256']:
                    raise AhaVerificationError('reviewed document bytes changed',references=references)
                return content,ref
            finally:
                response.close()
        except httpx.TransportError:
            if attempt==MAX_ATTEMPTS-1:
                raise AhaVerificationError('public source transport failed',references=references) from None
            time.sleep(2**attempt)
    raise AhaVerificationError('public source retries exhausted',references=references)


def _document_text(document, content):
    try:
        if document['format']=='pdf':
            reader=PdfReader(BytesIO(content),strict=True)
            if reader.is_encrypted or not reader.pages or len(reader.pages)>100:
                raise ValueError('invalid PDF')
            pages=[p.extract_text() or '' for p in reader.pages]
        else:
            pages=[text(content.decode('utf-8'))]
        if not any(p.strip() for p in pages):raise ValueError('empty text')
        return [unicodedata.normalize('NFKC',' '.join(p.split())) for p in pages]
    except Exception:
        raise AhaVerificationError('unreadable reviewed document; review required') from None


def _assertions(document,pages):
    for check in document.get('assertions',[]):
        region=pages[check['page']-1] if check.get('page') else ' '.join(pages)
        if not re.search(check['pattern'],region,re.I):
            raise AhaVerificationError('document material assertion failed: '+check['key'])


def _date_pattern(day):
    value=date.fromisoformat(day)
    month=value.strftime('%B'); short=value.strftime('%b')
    return r'(?:'+month+'|'+short+r'\.?)\s+'+str(value.day)+r',?\s+'+str(value.year)


def _date_role(program, field, label, cover):
    """Bind the date to its Key Dates label, rather than any date in the PDF.

    These are the reviewed two-program English RFP layouts. An unfamiliar or
    contradictory label/date is a review failure, not a guessed new parser rule.
    """
    weekday = (r'(?:(?:Mon(?:day)?|Tue(?:s(?:day)?)?|Wed(?:nesday)?|'
               r'Thu(?:rs(?:day)?)?|Fri(?:day)?|Sat(?:urday)?|Sun(?:day)?)\.?[,]?\s+)?')
    date_value = r'([A-Za-z]+\.?\s+\d{1,2},?\s+\d{4})'
    labels = list(re.finditer(r'\b' + label + r'\s*:\s*', cover, re.I))
    values = [re.match(weekday + date_value, cover[match.end():], re.I) for match in labels]
    if not values or any(value is None or not re.fullmatch(
            _date_pattern(program[field]), value[1], re.I) for value in values):
        raise AhaVerificationError('document date role contradicts reviewed terms')


def _program_assertions(program,manifest,pages):
    joined=' '.join(pages)
    name=program['title'].removeprefix(str(manifest['cycle'])+' ')
    cover=pages[0]
    if not re.search(r'(?<!\d)'+re.escape(str(manifest['cycle']))+r'(?!\d)',cover) or not re.search(re.escape(name),cover,re.I):
        raise AhaVerificationError('document cover identity/cycle mismatch')
    for field in ['total_usd','annual_usd']:
        value=program[field]
        if not any(re.search(r'(?<!\d)'+re.escape(a)+r'(?!\d)',joined) for a in [str(value),f'{value:,}']):
            raise AhaVerificationError('document budget contradicts reviewed terms')
    months=program['months']; years=months//12
    word={1:'one',2:'two',3:'three',4:'four',5:'five'}.get(years,str(years))
    period=r'(?:'+str(months)+r'\s*months?'+(r'|(?:'+str(years)+'|'+word+r')\s*[- ]?years?' if months%12==0 else '')+')'
    if not re.search(period,joined,re.I):
        raise AhaVerificationError('document period contradicts reviewed terms')
    roles = {'opens_date': r'ProposalCentral\s+open', 'award_start_date': r'Award\s+start'}
    if program['key'] == 'innovative-project-award':
        roles.update(deadline_date=r'Pre[ -]?proposal\s+deadline',
                     invitation_date=r'Invitation\s+to\s+submit\s+full\s+proposal',
                     invited_full_deadline_date=r'Invited\s+full\s+proposal\s+deadline')
    else:
        roles['deadline_date'] = r'Proposal\s+deadline'
    for field, label in roles.items():
        _date_role(program, field, label, cover)
    if not re.search(r'3\s*p\.?\s*m\.?\s*Central',joined,re.I):
        raise AhaVerificationError('document submission time contradicts reviewed terms')
    if program['deadline_stage']=='pre_proposal':
        if not re.search(r'pre[ -]?proposal',joined,re.I) or not re.search(r'invit',joined,re.I):
            raise AhaVerificationError('document initial/invited stages contradict reviewed terms')
    elif not re.search(r'application',joined,re.I):
        raise AhaVerificationError('document application stage missing')


def _normalize(program,manifest,reference,general_ref):
    cycle=str(manifest['cycle']);key=program['key'];source_id=cycle+'-'+key
    local=_local_deadline(program['deadline_date'],program['deadline_time']);due=local.astimezone(timezone.utc).isoformat()
    stage={'stage':program['deadline_stage'],'opens_date':program['opens_date'],'deadline_at':due,'required':True,'invitation_required':False}
    stages=[stage]
    if program.get('invited_full_deadline_date'):
        invited=_local_deadline(program['invited_full_deadline_date'])
        stages.append({'stage':'full_application','deadline_at':invited.astimezone(timezone.utc).isoformat(),
                       'required':True,'invitation_required':True,'invitation_date':program['invitation_date']})
    note=f"{program['deadline_stage']} due {program['deadline_date']} at 3 p.m. Central."
    if len(stages)>1:note+=' Later full application is invitation-only; its date does not extend entry for new applicants.'
    ref={**reference,'source_id':source_id,'canonical_url':program['source_url'],'reviewed_date':manifest['reviewed_date'],'document_revision':next(d.get('document_revision') for d in manifest['documents'] if d['key']==program['document'])}
    fields={
        'title_normalized':program['locators']['title_normalized'],'sponsor_normalized':'RFP issuer/header',
        'opportunity_number':'Derived internal identity, not an issuer-assigned solicitation number',
        'dedupe_key':'Derived SHA-256: aha|cycle|reviewed program slug','source_ids':'Reviewed cycle and program identity',
        'deadline_parsed':program['locators']['application_stages']+'; UTC midnight date index only',
        'source_deadline_date':program['locators']['application_stages'],'deadline_precision':'Date index; exact time stored separately',
        'deadline_description':program['locators']['application_stages'],'deadline_stage':program['locators']['application_stages'],
        'submission_deadline_at':program['locators']['application_stages'],'submission_deadline_local':program['locators']['application_stages'],
        'submission_deadline_timezone':program['locators']['application_stages'],'application_stages':program['locators']['application_stages'],
        'eligibility_parsed':program['locators']['eligibility_parsed'],'eligibility_geography':program['locators']['eligibility_parsed']+'; reviewed national host scope',
        'award_amount_parsed':program['locators']['award_amount_parsed'],'award_period_months':program['locators']['award_period_months'],
        'award_amount_basis':program['locators']['award_amount_parsed'],'description':program['locators']['description'],
    }
    geography=dict(program.get('geographic_policy') or manifest['geographic_policy'])
    r={'source':'aha','opportunity_id':'aha-'+source_id,'opportunity_number':'AHA-'+cycle+'-'+key.upper(),
       'dedupe_key':hashlib.sha256(('aha|'+cycle+'|'+key).encode()).hexdigest(),
       'title_normalized':text(program['title']),'sponsor_normalized':'American Heart Association',
       'deadline_parsed':program['deadline_date']+'T00:00:00+00:00','source_deadline_date':program['deadline_date']+'T00:00:00+00:00',
       'deadline_precision':'date','deadline_description':note,'submission_deadline_at':due,'submission_deadline_local':local.isoformat(),
       'submission_deadline_timezone':'America/Chicago','deadline_stage':program['deadline_stage'],'application_stages':stages,
       'eligibility_parsed':list(program['eligibility']),'eligibility_geography':geography,
       'award_amount_parsed':{'currency':'USD','floor':None,'ceiling':amount(program['total_usd']),
                              'note':'Total program budget; '+program['indirect_note']},
       'award_period_months':program['months'],'award_amount_basis':'total','source_ids':[{'source':'aha','id':source_id}],
       'description':text(program['description']),'fetched_at':reference['fetched_at'],'updated_at':reference['fetched_at'],
       'source_refs':{name:[{**ref,'field':locator}] for name,locator in fields.items()},'change_log':[],
       'quality_flags':['reviewed_aha_subset','research_coverage_not_collected'],
       'links':[],'linked_awards':[],'linked_papers':[],'linked_trials':[],'linked_nsf_program_awards':[],
       'research_coverage':{'opportunity_provider':'aha','status':'not_collected','note':'AHA awards/papers not collected; absence is not evidence of a research gap.'},
       'join_status':'outside_current_research_coverage'}
    r['source_refs']['eligibility_parsed'].append({**general_ref,'source_id':source_id,'field':'Verified general application requirements','reviewed_date':manifest['reviewed_date'],'document_revision':next(d.get('document_revision') for d in manifest['documents'] if d['key']==manifest['general_requirements_document'])})
    return r


def collect(manifest_path,raw_dir,now,client=None):
    _aware(now)
    if manifest_path is None:
        return AhaBatch(scope={'provider':'aha','enabled':False},verification={'status':'disabled'},
                        counts={'aha_reviewed_programs':0,'aha_admitted_opportunities':0,'aha_excluded_programs':0})
    manifest=load_manifest(manifest_path)
    documents={d['key']:d for d in manifest['documents']}
    if any(d.get('review_status')!='verified' or not d.get('expected_sha256') for d in documents.values()):
        raise AhaVerificationError('required general/application source review is incomplete')
    references=[];verified={};run=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid4().hex
    owned=client is None;client=client or httpx.Client(timeout=TIMEOUT,follow_redirects=False,trust_env=True)
    try:
        for key,document in documents.items():
            content,ref=_fetch(document,raw_dir,run,client,references)
            pages=_document_text(document,content);_assertions(document,pages);verified[key]=(pages,ref)
        records=[];excluded=[]
        general=verified[manifest['general_requirements_document']][1]
        for program in manifest['programs']:
            pages,ref=verified[program['document']]
            _program_assertions(program,manifest,pages)
            r=_normalize(program,manifest,ref,general)
            if not (r['eligibility_geography'].get('country')=='US' and r['eligibility_geography'].get('scope')=='nationwide' and not r['eligibility_geography'].get('state_restrictions')):
                excluded.append({'source_id':r['source_ids'][0]['id'],'reason':'outside_nationwide_geographic_policy'});continue
            if not open_to_new_applicants(r,now):
                excluded.append({'source_id':r['source_ids'][0]['id'],'reason':'closed_to_new_applicants'});continue
            records.append(r)
        if len({r['opportunity_id'] for r in records})!=len(records) or len({r['dedupe_key'] for r in records})!=len(records):
            raise AhaVerificationError('duplicate admitted identity')
        return AhaBatch(records=records,scope={'provider':'aha','cycle':str(manifest['cycle']),
                        'reviewed_programs':sorted(p['key'] for p in manifest['programs']),
                        'geographic_policy':manifest['geographic_policy'],'reviewed_subset':True,'manifest_sha256':manifest['_sha256']},
                        references=references,verification={'status':'verified','verified_at':_stamp(),
                            'reviewed_at':manifest['reviewed_date'],'scope':'reviewed_subset_not_directory_discovery',
                            'excluded':excluded,'documents':{k:{'content_sha256':v[1]['content_sha256'],'fetched_at':v[1]['fetched_at']} for k,v in verified.items()}},
                        counts={'aha_reviewed_programs':len(manifest['programs']),'aha_admitted_opportunities':len(records),'aha_excluded_programs':len(excluded)})
    except AhaVerificationError as exc:
        exc.references=list(references);exc.refs=exc.references
        raise
    finally:
        if owned:client.close()
