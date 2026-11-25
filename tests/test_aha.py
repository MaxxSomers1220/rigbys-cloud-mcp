"""Deterministic source-verification tests with self-authored synthetic PDFs only.

These fixtures do not constitute production general-rules review or live access.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import gzip

import httpx
import pytest

from rigbys_feed import aha
from rigbys_feed.scoring import score

NOW = datetime(2026,11,24,18,tzinfo=timezone.utc)


def pdf_bytes(body):
    lines=body.splitlines()
    # A minimal genuine PDF containing only this test's own text. No funder PDF
    # or licensed source content is redistributed in the test repository.
    ops=['BT /F1 9 Tf 40 760 Td']
    for i,line in enumerate(lines):
        if i:ops.append('0 -13 Td')
        value=line.replace('\\','\\\\').replace('(','\\(').replace(')','\\)')
        ops.append('('+value+') Tj')
    stream=('\n'.join(ops)+'\nET').encode()
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Count 1 /Kids [3 0 R] >>',
             b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
             b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
             b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream']
    output=bytearray(b'%PDF-1.4\n');offsets=[0]
    for i,obj in enumerate(objects,1):
        offsets.append(len(output));output+=str(i).encode()+b' 0 obj\n'+obj+b'\nendobj\n'
    cross=len(output);output+=b'xref\n0 6\n0000000000 65535 f \n'
    for offset in offsets[1:]:output+=f'{offset:010} 00000 n \n'.encode()
    output+=b'trailer << /Size 6 /Root 1 0 R >>\nstartxref\n'+str(cross).encode()+b'\n%%EOF\n'
    return bytes(output)


def program_text(p,cycle):
    name=p['title'].removeprefix(str(cycle)+' ')
    roles = {'opens_date':'ProposalCentral open', 'deadline_date':
             'Pre-proposal deadline' if p['key']=='innovative-project-award' else 'Proposal deadline',
             'invitation_date':'Invitation to submit full proposal',
             'invited_full_deadline_date':'Invited full proposal deadline', 'award_start_date':'Award start'}
    dates='\n'.join(label+': '+datetime.fromisoformat(p[k]).strftime('%B %-d, %Y') for k,label in roles.items() if p.get(k))
    return (f'{cycle} American Heart Association {name}\n{dates}\n'
            f"Total budget ${p['total_usd']:,}; annual budget ${p['annual_usd']:,}; duration {p['months']} months.\n"
            'All applications due 3 p.m. Central; includes 10% indirect costs.\n'
            'Eligible U.S. nonprofit institutions; doctoral Ph.D. degree required.\n'
            'Assistant professor level; within six years; training/career interruption exceptions.\n'
            'Primary mentor and secondary mentor; 10% effort; R01 and K99/R00 prior award restrictions.\n'
            'Professional Membership and institutional sign-off; same project limited to three submissions.\n'
            'Permitted citizenship/permanent resident/I-485/E-3/G-4/H1-B/O-1/TN/DACA status required.\n'
            'Beyond fellow or training; peer review and reviewer registration required.\n'
            'No previous AHA submission; preliminary data prohibited; blinded pre-proposal mandatory.\n'
            'Later full application is invitation only.')


def write_manifest(tmp_path,manifest):
    manifest['review_binding_sha256']=aha.review_binding(manifest)
    path=tmp_path/'reviewed.json';path.write_text(json.dumps(manifest));return path


@pytest.fixture
def reviewed(tmp_path):
    manifest=json.loads(aha.default_manifest_path().read_text())
    content={}
    for p in manifest['programs']:
        document=next(d for d in manifest['documents'] if d['key']==p['document'])
        body=pdf_bytes(program_text(p,manifest['cycle']))
        content[document['url']]=body
        document['expected_sha256']=hashlib.sha256(body).hexdigest()
        document['review_status']='verified'
        p['expected_content_sha256']=document['expected_sha256']
    general=next(d for d in manifest['documents'] if d['key']==manifest['general_requirements_document'])
    content[general['url']]=b'<html><h1>AHA Application Requirements</h1><p>Professional membership, institutional authorization and permitted immigration citizenship or permanent resident status are required.</p></html>'
    general['expected_sha256']=hashlib.sha256(content[general['url']]).hexdigest();general['review_status']='verified'
    return manifest,content,write_manifest(tmp_path,manifest)


def client_for(content, calls=None):
    def handle(request):
        if calls is not None:calls.append(request)
        body=content[str(request.url)]
        return httpx.Response(200,content=body,headers={'Content-Type':'application/pdf' if body.startswith(b'%PDF') else 'text/html','Content-Length':str(len(body))})
    return httpx.Client(transport=httpx.MockTransport(handle),headers={'Authorization':'must-not-be-forwarded','Cookie':'must-not-be-forwarded'},cookies={'session':'must-not-be-forwarded'})


def collect(reviewed,tmp_path,now=NOW,client=None):
    return aha.collect(reviewed[2],tmp_path/'raw',now,client=client or client_for(reviewed[1]))


def test_disabled_does_not_request_or_touch_raw(tmp_path):
    batch=aha.collect(None,tmp_path/'raw',NOW,client=httpx.Client(transport=httpx.MockTransport(lambda r:pytest.fail('Disabled AHA made request'))))
    assert batch.records==[] and batch.verification['status']=='disabled'
    assert batch.counts=={'aha_reviewed_programs':0,'aha_admitted_opportunities':0,'aha_excluded_programs':0}
    assert not (tmp_path/'raw').exists()


def test_committed_manifest_truthfully_blocks_general_rules(tmp_path):
    m=aha.load_manifest(aha.default_manifest_path())
    assert m['enabled_by_default'] is False
    general=next(d for d in m['documents'] if d['key']==m['general_requirements_document'])
    assert general['review_status']=='unverified' and general['expected_sha256'] is None
    with pytest.raises(aha.AhaVerificationError,match='incomplete'):
        aha.collect(aha.default_manifest_path(),tmp_path,NOW,client=httpx.Client(transport=httpx.MockTransport(lambda r:pytest.fail('No verified prerequisite'))))


def test_fresh_verification_full_fidelity_and_archive(reviewed,tmp_path):
    calls=[];batch=collect(reviewed,tmp_path,client=client_for(reviewed[1],calls))
    assert len(calls)==3 and all(r.method=='GET' for r in calls)
    assert all('authorization' not in r.headers and 'cookie' not in r.headers for r in calls)
    assert all(r.headers['accept-encoding']=='identity' for r in calls)
    assert len(batch.records)==2 and batch.verification['status']=='verified'
    assert datetime.fromisoformat(batch.verification['verified_at']).tzinfo is not None
    assert batch.counts=={'aha_reviewed_programs':2,'aha_admitted_opportunities':2,'aha_excluded_programs':0}
    assert batch.references==batch.refs and len(batch.refs)==3
    assert not list((tmp_path/'raw').glob('*/*.json')),'AHA envelopes cannot enter ResumeClient JSON-response scan'
    for ref in batch.refs:
        raw=Path(ref['raw_path']).read_bytes();assert hashlib.sha256(raw).hexdigest()==ref['sha256']
        envelope=json.loads(raw);document=Path(envelope['document_path']).read_bytes()
        assert hashlib.sha256(document).hexdigest()==ref['content_sha256']
        assert envelope['method']=='GET'
    for r,p in zip(batch.records,reviewed[0]['programs']):
        assert r['source']=='aha'
        assert r['opportunity_id']=='aha-2027-'+p['key']
        assert r['dedupe_key']==hashlib.sha256(('aha|2027|'+p['key']).encode()).hexdigest()
        assert r['eligibility_parsed']==p['eligibility']
        assert r['award_amount_parsed']['ceiling']==p['total_usd'] and r['award_amount_parsed']['floor'] is None
        assert r['award_amount_basis']=='total' and r['award_period_months']==p['months']
        assert '10%' in r['award_amount_parsed']['note']
        assert r['deadline_parsed']==p['deadline_date']+'T00:00:00+00:00'
        assert r['deadline_precision']=='date' and r['submission_deadline_at'].endswith('21:00:00+00:00')
        assert r['deadline_stage']==p['deadline_stage']
        assert r['join_status']=='outside_current_research_coverage'
        assert r['linked_awards']==r['linked_papers']==r['linked_trials']==r['linked_nsf_program_awards']==r['links']==[]
        for key in ['title_normalized','eligibility_parsed','award_amount_parsed','application_stages','eligibility_geography']:
            assert r['source_refs'][key][0]['content_sha256'] and r['source_refs'][key][0]['field']
            assert r['source_refs'][key][0]['reviewed_date']=='2026-11-24'
            assert r['source_refs'][key][0]['document_revision'] is None
        score(r,NOW.date())
        assert [r[k] for k in ['growth_score','momentum_score','novelty_score','gap_score']]==[50]*4
        assert r['score_evidence']['status']=='insufficient_data_neutral_placeholder'


@pytest.mark.parametrize('state',aha.STATES)
def test_all_fifty_state_geography_is_conditional_not_individual_approval(reviewed,tmp_path,state):
    for r in collect(reviewed,tmp_path).records:
        assert aha.geographic_screen(r,state)
        assert 'not individual' in r['eligibility_geography']['basis']
        assert r['eligibility_parsed']


def test_state_restricted_reviewed_variant_excluded(reviewed,tmp_path):
    m,content,path=reviewed;m['programs'][0]['geographic_policy']={'country':'US','scope':'regional','state_restrictions':['TX'],'basis':'Synthetic state-restricted supplement fixture'}
    path=write_manifest(tmp_path,m);batch=aha.collect(path,tmp_path/'raw',NOW,client_for(content))
    assert [r['opportunity_id'] for r in batch.records]==['aha-2027-innovative-project-award']
    assert batch.counts['aha_excluded_programs']==1
    assert not aha.geographic_screen({'eligibility_geography':m['programs'][0]['geographic_policy']},'TX')


@pytest.mark.parametrize('kind',['career-development-award','innovative-project-award'])
def test_initial_gate_before_at_after_and_invited_stage_never_reopens(reviewed,tmp_path,kind):
    r=next(r for r in collect(reviewed,tmp_path).records if r['opportunity_id'].endswith(kind))
    due=datetime.fromisoformat(r['submission_deadline_at'])
    assert aha.open_to_new_applicants(r,due-timedelta(microseconds=1))
    assert not aha.open_to_new_applicants(r,due)
    assert not aha.open_to_new_applicants(r,due+timedelta(microseconds=1))
    assert not aha.open_to_new_applicants(r,datetime(2027,2,1,tzinfo=timezone.utc))
    with pytest.raises(ValueError):aha.open_to_new_applicants(r,datetime(2026,11,24))
    assert not aha.open_to_new_applicants(r,datetime(2026,9,30,23,tzinfo=timezone.utc))


def test_timezone_dst_conversion_is_zoneinfo_not_fixed_offset():
    assert aha._local_deadline('2027-03-04').astimezone(timezone.utc).hour==21
    assert aha._local_deadline('2027-03-15').astimezone(timezone.utc).hour==20


def test_expired_batch_still_freshly_verifies_every_required_document(reviewed,tmp_path):
    calls=[];batch=collect(reviewed,tmp_path,datetime(2027,3,1,tzinfo=timezone.utc),client_for(reviewed[1],calls))
    assert len(calls)==3 and batch.records==[] and batch.verification['status']=='verified'
    assert batch.counts['aha_reviewed_programs']==batch.counts['aha_excluded_programs']==2
    assert batch.references


@pytest.mark.parametrize('status',[403,401,404])
def test_http_denials_never_retry_or_succeed_empty(reviewed,tmp_path,status):
    calls=[]
    def denied(r):calls.append(r);return httpx.Response(status,content=b'blocked',headers={'Content-Type':'text/html'})
    with pytest.raises(aha.AhaVerificationError,match='HTTP '+str(status)) as error:collect(reviewed,tmp_path,client=httpx.Client(transport=httpx.MockTransport(denied)))
    assert len(calls)==1 and len(error.value.references)==1
    assert Path(error.value.refs[0]['raw_path']).is_file()


@pytest.mark.parametrize('status',[429,500,503])
def test_retry_is_bounded(reviewed,tmp_path,monkeypatch,status):
    calls=[];delays=[];monkeypatch.setattr(aha.time,'sleep',delays.append)
    def unavailable(r):calls.append(r);return httpx.Response(status,content=b'retry',headers={'Retry-After':'100000'})
    with pytest.raises(aha.AhaVerificationError,match='retries exhausted'):collect(reviewed,tmp_path,client=httpx.Client(transport=httpx.MockTransport(unavailable)))
    assert len(calls)==5 and delays==[16]*4
    assert len(list((tmp_path/'raw').rglob('*.bin')))==5


def test_transport_retry_is_bounded_and_does_not_resume_old_archive(reviewed,tmp_path,monkeypatch):
    calls=[];delays=[];monkeypatch.setattr(aha.time,'sleep',delays.append)
    collect(reviewed,tmp_path)
    def broken(r):calls.append(r);raise httpx.ConnectError('secret transport text',request=r)
    with pytest.raises(aha.AhaVerificationError,match='transport failed') as error:collect(reviewed,tmp_path,client=httpx.Client(transport=httpx.MockTransport(broken)))
    assert len(calls)==5 and delays==[1,2,4,8]
    assert 'secret' not in str(error.value)


@pytest.mark.parametrize('case',['html','mime','empty','length','oversize','hash','unapproved_redirect','wrong_identity','wrong_cycle','budget','period','date'])
def test_invalid_or_changed_sources_fail_closed(reviewed,tmp_path,monkeypatch,case):
    m,content,path=reviewed;first=m['documents'][0];body=content[first['url']];headers={'Content-Type':'application/pdf'};status=200
    if case=='html':body=b'<html>login</html>'
    if case=='mime':headers['Content-Type']='text/html'
    if case=='empty':body=b''
    if case=='length':headers['Content-Length']=str(len(body)+10)
    if case=='oversize':monkeypatch.setattr(aha,'MAX_BYTES',20)
    if case=='hash':body+=b'changed version'
    if case=='unapproved_redirect':status=302;headers['Location']='https://login.example.test/credentials'
    if case in {'wrong_identity','wrong_cycle','budget','period','date'}:
        source=program_text(m['programs'][0],m['cycle'])
        source=source.replace('Career Development Award','Wrong Program') if case=='wrong_identity' else source
        source=source.replace('2027 American','2028 American') if case=='wrong_cycle' else source
        source=source.replace('231,000','232,000') if case=='budget' else source
        source=source.replace('36 months','48 months') if case=='period' else source
        source=source.replace('December 1, 2026','December 2, 2026') if case=='date' else source
        body=pdf_bytes(source);first['expected_sha256']=hashlib.sha256(body).hexdigest()
        m['programs'][0]['expected_content_sha256']=first['expected_sha256'];path=write_manifest(tmp_path,m)
    def bad(r):return httpx.Response(status,content=body,headers=headers)
    with pytest.raises(aha.AhaVerificationError):aha.collect(path,tmp_path/'raw',NOW,httpx.Client(transport=httpx.MockTransport(bad)))
    assert list((tmp_path/'raw').rglob('*.bin')),'Bytes archived before semantic validation'


def test_explicit_approved_redirect_and_gzip_are_bounded(reviewed,tmp_path):
    m,content,path=reviewed;first=m['documents'][0];target=m['programs'][0]['source_url'];first['approved_redirects']=[target];path=write_manifest(tmp_path,m);calls=[]
    def redirected(r):
        calls.append(str(r.url))
        if str(r.url)==first['url']:return httpx.Response(302,headers={'Location':target})
        body=content[first['url']] if str(r.url)==target else content[str(r.url)]
        packed=gzip.compress(body)
        return httpx.Response(200,content=packed,headers={'Content-Type':'application/pdf' if body.startswith(b'%PDF') else 'text/html','Content-Encoding':'gzip','Content-Length':str(len(packed))})
    batch=aha.collect(path,tmp_path/'raw',NOW,httpx.Client(transport=httpx.MockTransport(redirected)))
    assert len(batch.records)==2 and len(calls)==4
    assert batch.references[1]['final_url']==target


@pytest.mark.parametrize('change',['deadline','months','stage','eligibility','geography','partial_program','duplicate_program','prerequisite_swap','missing_assertion'])
def test_material_review_binding_and_scope_fail_on_silent_edits(reviewed,tmp_path,change):
    m,content,path=reviewed
    if change=='deadline':m['programs'][0]['deadline_date']='2030-12-01'
    if change=='months':m['programs'][0]['months']=48
    if change=='stage':m['programs'][1]['deadline_stage']='full_application'
    if change=='eligibility':m['programs'][0]['eligibility']=['Everyone is eligible']
    if change=='geography':m['geographic_policy']['state_restrictions']=['TX']
    if change=='partial_program':m['programs'].pop()
    if change=='duplicate_program':m['programs'].append(deepcopy(m['programs'][0]))
    if change=='prerequisite_swap':m['general_requirements_document']=m['programs'][0]['document']
    if change=='missing_assertion':m['documents'][-1]['assertions']=[]
    path.write_text(json.dumps(m))  # Deliberately NOT a new reviewed binding.
    with pytest.raises(aha.AhaVerificationError):aha.collect(path,tmp_path/'raw',NOW,client_for(content))


def test_two_fresh_retrievals_are_semantically_idempotent(reviewed,tmp_path,monkeypatch):
    from rigbys_feed.database import _semantic
    calls=[];client=client_for(reviewed[1],calls)
    monkeypatch.setattr(aha,'_stamp',lambda:'2026-11-24T18:00:00+00:00');first=collect(reviewed,tmp_path,client=client)
    monkeypatch.setattr(aha,'_stamp',lambda:'2026-11-24T18:01:00+00:00');second=collect(reviewed,tmp_path,client=client)
    assert len(calls)==6
    assert first.references[0]['raw_path']!=second.references[0]['raw_path']
    assert first.references[0]['fetched_at']!=second.references[0]['fetched_at']
    assert first.references[0]['content_sha256']==second.references[0]['content_sha256']
    assert [_semantic(r) for r in first.records]==[_semantic(r) for r in second.records]


@pytest.mark.parametrize('change', ['career_award_start', 'innovative_invited', 'innovative_stage',
                                   'conflicting_label', 'unknown_label', 'general_alias', 'duration',
                                   'canonical_url', 'document_url', 'document_key', 'program_hash'])
def test_explicit_new_review_cannot_hide_a_wrong_source_date_role_or_gate(reviewed,tmp_path,change):
    m,content,_ = reviewed
    if change=='career_award_start':
        m['programs'][0]['deadline_date']=m['programs'][0]['award_start_date']
    elif change=='innovative_invited':
        m['programs'][1]['deadline_date']=m['programs'][1]['invited_full_deadline_date']
        # Keep manifest date ordering valid so source role checking is exercised.
        m['programs'][1]['invitation_date']='2027-03-05'
        m['programs'][1]['invited_full_deadline_date']='2027-03-06'
    elif change=='innovative_stage':
        m['programs'][1]['deadline_stage']='full_application'
        m['programs'][1]['deadline_date']=m['programs'][1]['invited_full_deadline_date']
    elif change in {'conflicting_label','unknown_label'}:
        document=m['documents'][0]
        value='TBD' if change=='unknown_label' else 'December 2, 2026'
        body=pdf_bytes(program_text(m['programs'][0],m['cycle'])+'\nProposal deadline: '+value)
        content[document['url']]=body
        document['expected_sha256']=hashlib.sha256(body).hexdigest()
        m['programs'][0]['expected_content_sha256']=document['expected_sha256']
    elif change=='general_alias':
        m['general_requirements_document']=m['programs'][0]['document']
    elif change=='duration':
        m['programs'][0]['months']=1
    elif change=='canonical_url':
        m['programs'][0]['source_url']=m['programs'][1]['source_url']
    elif change=='document_url':
        m['documents'][0]['url']=m['documents'][1]['url']
    elif change=='document_key':
        m['documents'][0]['key']='../../escape'
        m['programs'][0]['document']='../../escape'
    elif change=='program_hash':
        m['programs'][0]['expected_content_sha256']='0'*64
    path=write_manifest(tmp_path,m)  # A new digest cannot make contradictory source facts true.
    with pytest.raises(aha.AhaVerificationError):
        aha.collect(path,tmp_path/'raw',NOW,client_for(content))


@pytest.mark.parametrize('weekday', ['Tues., ', 'Tuesday, ', 'Wed., ', 'Thurs., ', ''])
def test_reviewed_key_date_labels_accept_published_weekday_formatting(weekday):
    program={'deadline_date':'2026-12-01'}
    aha._date_role(program,'deadline_date',r'Proposal\s+deadline',
                   'Proposal deadline: '+weekday+'Dec. 1, 2026 Award start: April 1, 2027')


def test_reviewed_title_deadline_and_document_revision_do_not_rekey_cycle(reviewed,tmp_path):
    first=collect(reviewed,tmp_path).records[0]
    manifest,content,_=reviewed
    program=manifest['programs'][0]
    program['title']='2027 Revised Career Development Award'
    program['deadline_date']='2026-12-02'
    document=next(d for d in manifest['documents'] if d['key']==program['document'])
    document['document_revision']='synthetic-v2'
    body=pdf_bytes(program_text(program,manifest['cycle']))
    document['expected_sha256']=hashlib.sha256(body).hexdigest()
    program['expected_content_sha256']=document['expected_sha256']
    content[document['url']]=body
    path=write_manifest(tmp_path,manifest)
    revised=aha.collect(path,tmp_path/'raw',NOW,client_for(content)).records[0]
    assert revised['opportunity_id']==first['opportunity_id']
    assert revised['dedupe_key']==first['dedupe_key']
    assert revised['title_normalized']!=first['title_normalized']
    assert revised['submission_deadline_at']!=first['submission_deadline_at']
    assert revised['source_refs']['title_normalized'][0]['document_revision']=='synthetic-v2'


def test_reviewed_new_annual_cycle_has_new_identity(reviewed,tmp_path):
    manifest,content,_=reviewed
    manifest['cycle']='2028'
    for program in manifest['programs']:
        program['title']=program['title'].replace('2027','2028')
        for field in ('opens_date','deadline_date','invitation_date','invited_full_deadline_date','award_start_date'):
            if program.get(field):
                day=datetime.fromisoformat(program[field]).date()
                program[field]=day.replace(year=day.year+1).isoformat()
        document=next(d for d in manifest['documents'] if d['key']==program['document'])
        body=pdf_bytes(program_text(program,manifest['cycle']))
        document['expected_sha256']=hashlib.sha256(body).hexdigest()
        program['expected_content_sha256']=document['expected_sha256']
        content[document['url']]=body
    path=write_manifest(tmp_path,manifest)
    new=aha.collect(path,tmp_path/'raw',datetime(2027,11,24,tzinfo=timezone.utc),client_for(content))
    assert len(new.records)==2
    for record,program in zip(new.records,manifest['programs']):
        assert record['opportunity_id']=='aha-2028-'+program['key']
        assert record['dedupe_key']==hashlib.sha256(('aha|2028|'+program['key']).encode()).hexdigest()
