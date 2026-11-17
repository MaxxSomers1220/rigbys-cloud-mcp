"""Extractive, source-bound summaries; never generate dates, amounts or eligibility."""


def summarize(record):
    title = record['title_normalized']
    description = record['description']
    purpose = description
    if len(purpose) > 240:
        purpose = purpose[:237].rsplit(' ',1)[0] + '…'
    if record['deadline_precision']=='rolling':
        deadline = 'Rolling submission; check individual round requirements.'
    elif record['deadline_parsed']:
        deadline = f"Source closing date: {record['deadline_parsed'][:10]} (date only; check announcement for time and rounds)."
    else:
        deadline = 'Closing date not specified; check source announcement.'
    amount = record['award_amount_parsed']
    if amount:
        bounds = []
        if amount['floor'] is not None:
            bounds.append(f"floor ${amount['floor']:,.2f}")
        if amount['ceiling'] is not None:
            bounds.append(f"ceiling ${amount['ceiling']:,.2f}")
        money = 'Source award bounds (USD): '+', '.join(bounds)+'.'
    else:
        money = 'Award bounds not specified.'
    categories = record['eligibility_parsed']
    who = 'Eligibility: '+ ('; '.join(categories[:2]) if categories else 'see source')
    if len(who)>180:
        who=who[:177].rsplit(' ',1)[0]+'…'
    who += '; full qualifications and restrictions are listed below.'
    record['summary_short'] = f"{record['sponsor_normalized']}: {purpose or title} {deadline} {money} {who}"
    record['extracted_requirements'] = list(categories)
    if record['deadline_description']:
        record['extracted_requirements'].append('Source deadline requirements: '+record['deadline_description'])
    record['source_refs']['summary_short'] = (
        record['source_refs']['description'] + record['source_refs']['sponsor_normalized'] +
        record['source_refs']['deadline_parsed'] + record['source_refs']['deadline_description'] +
        record['source_refs']['award_amount_parsed'] + record['source_refs']['eligibility_parsed'])
    record['source_refs']['extracted_requirements'] = (
        record['source_refs']['eligibility_parsed'] + record['source_refs']['deadline_description'])
    return record
