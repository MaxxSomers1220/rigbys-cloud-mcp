from rigbys_feed.joining import join


def test_exact_foa_core_and_pmid_only():
    opportunities=[{'opportunity_id':'gg-1','opportunity_number':'PA-25-301','source_refs':{},'source_ids':[]}]
    ref={'source':'nih_reporter','fetched_at':'2026-11-17T00:00:00Z'}
    awards=[{'record':{'opportunity_number':'PA-25-301','project_num':'5R01AI145687-07',
                      'core_project_num':'R01AI145687','appl_id':42,'fiscal_year':2026},'ref':ref},
            {'record':{'opportunity_number':'UNRELATED'},'ref':ref}]
    pubs=[{'record':{'coreproject':'R01AI145687','pmid':123,'applid':41},'ref':ref}]
    papers=[{'record':{'id':'https://openalex.org/W1','ids':{'pmid':'https://pubmed.ncbi.nlm.nih.gov/123'}},'ref':ref},
            {'record':{'id':'https://openalex.org/W2','ids':{'pmid':'https://pubmed.ncbi.nlm.nih.gov/124'}},'ref':ref}]
    result=join(opportunities,awards,pubs,papers)[0]
    assert len(result['linked_awards'])==1
    assert len(result['linked_papers'])==1
    assert result['linked_papers'][0]['join_confidence']==0.85
    assert result['linked_papers'][0]['evidence']['via_award']=='5R01AI145687-07'
    assert {e['link_type'] for e in result['links']}=={'award','paper'}


def test_no_link_does_not_invent_title_match():
    r=join([{'opportunity_id':'gg-1','opportunity_number':'NO-MATCH','source_refs':{},'source_ids':[]}],[],[],[])[0]
    assert r['linked_awards']==r['linked_papers']==r['links']==[]
    assert r['join_status']=='no_confirmed_award_in_scoped_sources'


def test_direct_openalex_award_metadata_not_title_guess():
    opportunities=[{'opportunity_id':'gg-1','opportunity_number':'PA-25-301','source_refs':{},'source_ids':[]}]
    ref={'source':'nih_reporter','fetched_at':'2026-11-17T00:00:00Z'}
    awards=[{'record':{'opportunity_number':'PA-25-301','project_num':'5R01AI145687-07',
                      'core_project_num':'R01AI145687','appl_id':42,'fiscal_year':2026},'ref':ref}]
    papers=[{'record':{'id':'https://openalex.org/W1','awards':[{'funder_award_id':'R01AI145687'}]},'ref':ref},
            {'record':{'id':'https://openalex.org/W2','awards':[{'funder_award_id':'UNRELATED'}]},'ref':ref}]
    result=join(opportunities,awards,[],papers)[0]
    assert [p['target_id'] for p in result['linked_papers']]==['https://openalex.org/W1']
    edge=result['linked_papers'][0]
    assert edge['evidence']['openalex_funder_award_id']=='R01AI145687'
    assert edge['join_confidence']==0.95
    assert edge['relationship']=='paper_reports_award_core_in_funding_metadata'


def test_direct_core_identifier_normalizes_case_and_space():
    opp=[{'opportunity_id':'gg-1','opportunity_number':'PA-25-301','source_refs':{},'source_ids':[]}]
    ref={'source':'nih_reporter','fetched_at':'2026-11-17T00:00:00Z'}
    awards=[{'record':{'opportunity_number':'PA-25-301','project_num':'5R01AI145687-07',
                      'core_project_num':'R01AI145687','appl_id':42,'fiscal_year':2026},'ref':ref}]
    papers=[{'record':{'id':'https://openalex.org/W1','awards':[{'funder_award_id':' r01ai145687 '}]},'ref':ref}]
    r=join(opp,awards,[],papers)[0]
    assert len(r['linked_papers'])==1
    assert r['linked_papers'][0]['evidence']['openalex_funder_award_id']==' r01ai145687 '
