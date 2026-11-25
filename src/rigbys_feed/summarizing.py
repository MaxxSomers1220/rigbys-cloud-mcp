"""Extractive, source-bound summaries; never generate dates, amounts or eligibility."""


def summarize(record):
    title = record['title_normalized']
    description = record['description']
    purpose = description
    if len(purpose) > 240:
        purpose = purpose[:237].rsplit(' ',1)[0] + '…'
    if record.get('submission_deadline_at'):
        label = record['deadline_stage'].replace('_', ' ')
        deadline = (f"Next required action: {label} by {record['submission_deadline_local']} "
                    f"({record['submission_deadline_timezone']}; {record['submission_deadline_at']} UTC instant).")
        for stage in record['application_stages']:
            if stage.get('invitation_required'):
                deadline += (f" Invited applicants only: {stage['stage'].replace('_', ' ')} by "
                             f"{stage['deadline_at']}. This later stage does not extend entry for new applicants.")
    elif record['deadline_precision']=='rolling':
        deadline = 'Rolling submission; check individual round requirements.'
    elif record['deadline_parsed']:
        deadline = f"Source closing date: {record['deadline_parsed'][:10]} (date only; check announcement for time and rounds)."
    else:
        deadline = 'Closing date not specified; check source announcement.'
    amount = record['award_amount_parsed']
    if amount and record.get('award_amount_basis') == 'total':
        money = (f"Source-stated total award (USD): ${amount['ceiling']:,.2f} over "
                 f"{record['award_period_months']} months. {amount['note']}")
    elif amount:
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
    for field in ('submission_deadline_at', 'submission_deadline_local', 'submission_deadline_timezone',
                  'deadline_stage', 'application_stages', 'award_amount_basis', 'award_period_months'):
        if field in record:
            record['source_refs']['summary_short'] += record['source_refs'][field]
    return record
