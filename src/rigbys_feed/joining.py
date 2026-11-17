"""Evidence-backed edges: exact FOA -> award -> core project PMID -> work."""
from collections import defaultdict


def pmid_for(work):
    return str((work.get('ids') or {}).get('pmid', '')).rstrip('/').rsplit('/', 1)[-1]


def join(opportunities, awards, publications, papers, coverage=None):
    awards_by_foa, pubs_by_core, papers_by_pmid = defaultdict(list), defaultdict(list), {}
    papers_by_core = defaultdict(list)
    for item in awards:
        awards_by_foa[item['record'].get('opportunity_number', '').upper()].append(item)
    for item in publications:
        pubs_by_core[item['record']['coreproject']].append(item)
    for item in papers:
        papers_by_pmid[pmid_for(item['record'])] = item
        for core in {a.get('funder_award_id') for a in item['record'].get('awards', []) if a.get('funder_award_id')}:
            papers_by_core[core.strip().upper()].append(item)
    for opp in opportunities:
        links, linked_awards, linked_papers = [], {}, {}
        for wrapped in awards_by_foa[opp['opportunity_number']]:
            award, award_ref = wrapped['record'], wrapped['ref']
            target = award['project_num']
            award_url = f'https://reporter.nih.gov/project-details/{award["appl_id"]}'
            evidence = {'opportunity_number': opp['opportunity_number'],
                        'appl_id': award['appl_id'], 'core_project_num': award['core_project_num'],
                        'source_refs': [award_ref]}
            edge = dict(opportunity_id=opp['opportunity_id'], link_type='award', target_id=target,
                        target_url=award_url, join_confidence=1.0,
                        relationship='award_reported_under_exact_opportunity_number', evidence=evidence)
            links.append(edge)
            linked_awards[target] = {**edge, 'fiscal_year': award['fiscal_year'],
                                      'award_amount': award.get('award_amount'),
                                      'title': award.get('project_title')}
            for paper_item in papers_by_core[award['core_project_num'].strip().upper()]:
                paper = paper_item['record']
                direct = dict(opportunity_id=opp['opportunity_id'], link_type='paper', target_id=paper['id'],
                              target_url=paper['id'], join_confidence=0.95,
                              relationship='paper_reports_award_core_in_funding_metadata',
                              evidence={**evidence, 'via_award':target,
                                        'openalex_funder_award_id':next(a['funder_award_id'] for a in paper.get('awards',[])
                                            if a.get('funder_award_id','').strip().upper()==award['core_project_num'].strip().upper()),
                                        'match_rule':'case-insensitive trimmed award core identifier',
                                        'source_refs':[award_ref,paper_item['ref']]})
                old = linked_papers.get(paper['id'])
                if old is None or old['join_confidence'] < direct['join_confidence']:
                    linked_papers[paper['id']] = {**direct, 'publication_year':paper.get('publication_year'),
                                                'title':paper.get('display_name') or paper.get('title')}
            for publication in pubs_by_core[award['core_project_num']]:
                pub, pub_ref = publication['record'], publication['ref']
                paper_item = papers_by_pmid.get(str(pub['pmid']))
                if not paper_item:
                    continue
                paper = paper_item['record']
                exact_application = str(pub.get('applid')) == str(award['appl_id'])
                edge = dict(opportunity_id=opp['opportunity_id'], link_type='paper', target_id=paper['id'],
                            target_url=paper['id'], join_confidence=0.95 if exact_application else 0.85,
                            relationship='publication_associated_with_award_core_project',
                            evidence={**evidence, 'via_award': target, 'pmid': str(pub['pmid']),
                                      'publication_appl_id': pub.get('applid'),
                                      'application_id_matches': exact_application,
                                      'source_refs': [award_ref, pub_ref, paper_item['ref']]})
                # One opportunity/work edge, prefer matching application proof when available.
                old = linked_papers.get(paper['id'])
                if old is None or old['join_confidence'] < edge['join_confidence']:
                    linked_papers[paper['id']] = {**edge, 'publication_year': paper.get('publication_year'),
                                                  'title': paper.get('display_name') or paper.get('title')}
        # Per-fiscal-year award numbers are unique enough for these source edges.
        award_edges = {e['target_id']: e for e in links}
        opp['linked_awards'] = sorted(linked_awards.values(), key=lambda x:x['target_id'])
        opp['linked_papers'] = sorted(linked_papers.values(), key=lambda x:x['target_id'])
        opp['links'] = sorted(list(award_edges.values()) +
                              [{k:v for k,v in p.items() if k not in {'title','publication_year'}}
                               for p in linked_papers.values()], key=lambda x:(x['link_type'],x['target_id']))
        opp['research_coverage'] = dict(coverage or {})
        opp['join_status'] = 'exact_identifier_links' if linked_awards else 'no_confirmed_award_in_scoped_sources'
        opp['source_refs']['linked_awards'] = [{'source':'nih_reporter',
            'evidence_field':'linked_awards[].evidence.source_refs',
            'note':'Each link carries its own source IDs, URLs, hashes and retrieval timestamps.'}]
        opp['source_refs']['linked_papers'] = [{'source':'openalex',
            'evidence_field':'linked_papers[].evidence.source_refs',
            'note':'Each link carries its own source IDs, URLs, hashes and retrieval timestamps.'}]
        opp['source_ids'] += [{'source':'nih_reporter','id':a['target_id']} for a in opp['linked_awards']]
        opp['source_ids'] += [{'source':'openalex','id':p['target_id']} for p in opp['linked_papers']]
    return opportunities
