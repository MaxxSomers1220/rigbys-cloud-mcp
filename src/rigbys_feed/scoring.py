"""Versioned descriptive research signals, not estimates of funding success."""
import math

METHODOLOGY_VERSION = 'research-signals-1.0.0'


def bounded(value):
    return round(max(0, min(100, value)))


def increase(recent, previous):
    return bounded(100 * max(0, recent - previous) / max(1, previous))


def describe_evidence(record, thin, complete_calendar_year, complete_fiscal_year):
    for links, field, kind, year in (
        (record['linked_papers'], 'publication_year', 'paper', complete_calendar_year),
        (record['linked_awards'], 'fiscal_year', 'award', complete_fiscal_year),
    ):
        for link in links:
            inputs = [f'{kind}_count']
            if link.get(field) == year:
                inputs.append(f'{kind}_recent')
            elif link.get(field) == year - 1:
                inputs.append(f'{kind}_previous')
            link['score_inputs'] = inputs

    record['score_evidence_detail'] = {
        'basis': 'neutral_placeholder' if thin else 'linked_research',
        'reason': ('Fewer than five confirmed awards or ten confirmed papers. The value 50 '
                   'is a neutral placeholder. The evidence below records the observed inputs.'
                   if thin else 'Each score uses the listed inputs from the confirmed links.'),
        'link_fields': {'award': 'linked_awards', 'paper': 'linked_papers'},
        'link_evidence_fields': ['target_id', 'target_url', 'join_confidence', 'score_inputs'],
        'scores': {
            'growth_score': {'inputs': ['paper_recent', 'paper_previous'],
                             'reason': 'Change in linked paper count across two complete calendar years.'},
            'momentum_score': {'inputs': ['award_recent', 'award_previous'],
                               'reason': 'Change in linked award count across two complete federal fiscal years.'},
            'novelty_score': {'inputs': ['paper_count'],
                              'reason': 'Inverse of the log-scaled total count of linked papers.'},
            'gap_score': {'inputs': ['paper_count', 'award_count'],
                          'reason': 'Relative volume of linked papers and awards under the published formula.'},
        },
    }


def score(record, as_of):
    # Use complete periods only, since a fiscal/calendar year in progress biases counts.
    complete_calendar_year = as_of.year - 1
    fiscal_year = as_of.year + (as_of.month >= 10)
    complete_fiscal_year = fiscal_year - 1
    papers, awards = record['linked_papers'], record['linked_awards']
    paper_recent = sum(p.get('publication_year') == complete_calendar_year for p in papers)
    paper_previous = sum(p.get('publication_year') == complete_calendar_year-1 for p in papers)
    award_recent = sum(a.get('fiscal_year') == complete_fiscal_year for a in awards)
    award_previous = sum(a.get('fiscal_year') == complete_fiscal_year-1 for a in awards)
    inputs = {'paper_count':len(papers),'award_count':len(awards),
              'paper_recent':paper_recent,'paper_previous':paper_previous,
              'paper_complete_year':complete_calendar_year,
              'award_recent':award_recent,'award_previous':award_previous,
              'award_complete_fiscal_year':complete_fiscal_year}
    thin = len(awards) < 5 or len(papers) < 10
    values = {'growth_score':increase(paper_recent,paper_previous),
              'momentum_score':increase(award_recent,award_previous),
              'novelty_score':bounded(100*(1-min(1,math.log1p(len(papers))/math.log1p(1000)))),
              'gap_score':bounded(100*len(papers)/max(1,len(papers)+5*len(awards)))}
    if thin:
        values = {key:50 for key in values}
    record.update(values)
    record['methodology_version'] = METHODOLOGY_VERSION
    record['score_evidence'] = {'status':'insufficient_data_neutral_placeholder' if thin else 'descriptive_proxy',
                                'inputs':inputs, 'interpretation':
                                'No funding prediction. No confirmed link does not mean no funding. '
                                'Broad parent FOAs describe broad portfolios, not topic-specific gaps.'}
    describe_evidence(record, thin, complete_calendar_year, complete_fiscal_year)
    for field in values:
        record['source_refs'][field] = [{'methodology_version':METHODOLOGY_VERSION,
            'methodology':'docs/scoring-methodology.md', 'inputs':inputs,
            'evidence_fields':['linked_awards','linked_papers'], 'as_of':as_of.isoformat()}]
    return record
