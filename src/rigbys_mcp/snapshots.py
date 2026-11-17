"""Immutable seven-day-delayed basic-field reads; no current-feed fallback."""
from datetime import datetime, timedelta, timezone


def capture_snapshot(conn, run_id):
    """Capture inside the caller's successful feed-publication transaction."""
    return conn.execute('SELECT rigbys_capture_free_snapshot(%s)',(run_id,)).fetchone()[0]


def _utc_now(value):
    if value is None:
        return datetime.now(timezone.utc)
    if not isinstance(value,datetime) or value.tzinfo is None:
        raise ValueError('as_of must be a timezone-aware timestamp')
    return value.astimezone(timezone.utc)


def search_free(conn, topic, sponsor=None, deadline_before=None, deadline_after=None,
                limit=10, as_of=None):
    """Read the newest eligible immutable snapshot using validated search inputs.

    Both original generation and actual database capture must be at least seven
    days old. Matching uses titles only; summaries and scores never participate.
    """
    cutoff=_utc_now(as_of)-timedelta(days=7)
    header=conn.execute('''SELECT snapshot_id,feed_generated_at FROM free_feed_snapshots AS snapshots
        WHERE feed_generated_at<=%s AND captured_at<=%s
          AND record_count=(SELECT count(*) FROM free_search_records AS rows
                            WHERE rows.snapshot_id=snapshots.snapshot_id)
        ORDER BY feed_generated_at DESC,captured_at DESC,snapshot_id DESC LIMIT 1''',
        (cutoff,cutoff)).fetchone()
    if header is None:
        return {'opportunities':[],'feed_generated_at':None,'status':'delayed_feed_unavailable',
                'notice':'No immutable feed snapshot has aged seven days yet. Free search never falls back to current data.'}
    conditions=["snapshot_id=%s", "to_tsvector('english',coalesce(title_normalized,'')) @@ plainto_tsquery('english',%s)"]
    params=[header[0],topic]
    if sponsor:
        # Repository already resolves aliases and validates length/nonemptiness.
        pattern='%'+sponsor.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
        conditions.append('sponsor_normalized ILIKE %s');params.append(pattern)
    if deadline_before:
        conditions.append('deadline_parsed::date<=%s');params.append(deadline_before)
    if deadline_after:
        conditions.append('deadline_parsed::date>=%s');params.append(deadline_after)
    rows=conn.execute('''SELECT opportunity_id,title_normalized,sponsor_normalized,
        deadline_parsed,award_amount_parsed,source_refs,fetched_at,deadline_precision
        FROM free_search_records WHERE '''+' AND '.join(conditions)+'''
        ORDER BY deadline_parsed ASC NULLS LAST,opportunity_id ASC LIMIT %s''',
        params+[min(limit,25)]).fetchall()
    fields=('opportunity_id','title_normalized','sponsor_normalized','deadline_parsed',
            'award_amount_parsed','source_refs','fetched_at','deadline_precision')
    records=[]
    generated=header[1].isoformat()
    for row in rows:
        record=dict(zip(fields,row))
        for field in ('deadline_parsed','fetched_at'):
            if record[field] is not None:
                record[field]=record[field].isoformat()
        record['feed_generated_at']=generated
        records.append(record)
    return {'opportunities':records,'feed_generated_at':generated,'status':'delayed_snapshot',
            'notice':'Immutable snapshot at least seven days old. Title-only matching; no scores or summaries. Check source deadlines and submission rounds.'}
