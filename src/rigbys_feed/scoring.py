"""Versioned descriptive research signals, not estimates of funding success."""
import math

METHODOLOGY_VERSION = 'research-signals-1.0.0'


def bounded(value):
    return round(max(0, min(100, value)))


def increase(recent, previous):
    return bounded(100 * max(0, recent - previous) / max(1, previous))


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
    for field in values:
        record['source_refs'][field] = [{'methodology_version':METHODOLOGY_VERSION,
            'methodology':'docs/scoring-methodology.md', 'inputs':inputs,
            'evidence_fields':['linked_awards','linked_papers'], 'as_of':as_of.isoformat()}]
    return record
