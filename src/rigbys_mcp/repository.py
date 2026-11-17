"""Parameterized, read-only queries over the persisted feed. No upstream API calls."""
from contextlib import contextmanager
from datetime import date
import os
import psycopg

SCORES = ('growth_score','momentum_score','novelty_score','gap_score')
SPONSORS = {'nih':'National Institutes of Health', 'nsf':'U.S. National Science Foundation'}
VECTOR = "to_tsvector('english', coalesce(title_normalized,'') || ' ' || coalesce(summary_short,''))"


class QueryError(ValueError):
    pass


def topic_value(topic):
    if not isinstance(topic,str) or not topic.strip() or len(topic)>500:
        raise QueryError('Topic must be a nonempty string of at most 500 characters')
    return topic.strip()


def iso_date(value):
    if value is None or isinstance(value,date):
        return value
    try:
        return date.fromisoformat(value)
    except (ValueError,TypeError):
        raise QueryError('Deadlines must be ISO dates') from None


def search_values(topic, sponsor, before, after, minimum, limit):
    topic = topic_value(topic)
    before, after = iso_date(before), iso_date(after)
    if before and after and before<after:
        raise QueryError('deadline_before must be on or after deadline_after')
    if minimum is not None and (type(minimum) is not int or not 0<=minimum<=100):
        raise QueryError('min_gap_score must be an integer from 0 to 100')
    if type(limit) is not int or limit<1:
        raise QueryError('limit must be a positive integer')
    if sponsor is not None:
        if not isinstance(sponsor,str) or not sponsor.strip() or len(sponsor)>200:
            raise QueryError('Sponsor must be a nonempty string of at most 200 characters')
        sponsor = SPONSORS.get(sponsor.strip().lower(),sponsor.strip())
    return topic,sponsor,before,after,minimum,min(limit,25)


@contextmanager
def read_connection():
    with psycopg.connect(os.environ['DATABASE_URL'],autocommit=True) as conn:
        with conn.transaction():
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            conn.execute("SET LOCAL TIME ZONE 'UTC'")
            yield conn


def literal_pattern(value):
    return '%'+value.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'


class Repository:
    def search(self, topic, sponsor=None, deadline_before=None, deadline_after=None,
               min_gap_score=None, limit=10):
        topic,sponsor,before,after,minimum,limit = search_values(
            topic,sponsor,deadline_before,deadline_after,min_gap_score,limit)
        conditions, params = [VECTOR+" @@ plainto_tsquery('english',%s)"], [topic]
        if sponsor:
            conditions.append('sponsor_normalized ILIKE %s');params.append(literal_pattern(sponsor))
        if before:
            conditions.append('deadline_parsed::date <= %s');params.append(before)
        if after:
            conditions.append('deadline_parsed::date >= %s');params.append(after)
        if minimum is not None:
            conditions.append("gap_score >= %s AND record#>>'{score_evidence,status}'='descriptive_proxy'");params.append(minimum)
        query = '''SELECT opportunity_id,title_normalized,sponsor_normalized,deadline_parsed,
            award_amount_parsed,growth_score,momentum_score,novelty_score,gap_score,
            methodology_version,summary_short,source_refs,feed_generated_at,
            record->'score_evidence',record->'join_status',record->'research_coverage',
            record->'deadline_precision',record->'deadline_description'
            FROM opportunities WHERE '''+' AND '.join(conditions)+''' ORDER BY
            deadline_parsed ASC NULLS LAST,opportunity_id ASC LIMIT %s'''
        with read_connection() as conn:
            rows=conn.execute(query,params+[limit]).fetchall()
            feed=conn.execute("SELECT max(feed_generated_at) FROM feed_runs WHERE status='success'").fetchone()[0]
        fields=('opportunity_id','title_normalized','sponsor_normalized','deadline_parsed',
                'award_amount_parsed',*SCORES,'methodology_version','summary_short','source_refs',
                'feed_generated_at','score_evidence','join_status','research_coverage',
                'deadline_precision','deadline_description')
        records=[]
        for row in rows:
            record=dict(zip(fields,row))
            for field in ('deadline_parsed','feed_generated_at'):
                if record[field] is not None: record[field]=record[field].isoformat()
            record['source_refs'] = {k:v for k,v in (record['source_refs'] or {}).items()
                if k in fields and k not in {'research_coverage','join_status'}}
            records.append(record)
        return {'opportunities':records, 'feed_generated_at':feed.isoformat() if feed else None,
                'notice':'Scores retain source evidence flags. Neutral placeholders are not observed funding gaps and are excluded when min_gap_score is requested; dates and freshness must be checked.'}

    def get(self, opportunity_id):
        opportunity_id = identifier_value(opportunity_id)
        with read_connection() as conn:
            row=conn.execute('SELECT record FROM opportunities WHERE opportunity_id=%s',(opportunity_id,)).fetchone()
        if row is None:
            raise QueryError('Opportunity not found')
        return row[0]



    def links(self, opportunity_id):
        opportunity_id=identifier_value(opportunity_id)
        with read_connection() as conn:
            exists=conn.execute('SELECT feed_generated_at FROM opportunities WHERE opportunity_id=%s',(opportunity_id,)).fetchone()
            if exists is None: raise QueryError('Opportunity not found')
            rows=conn.execute("""SELECT opportunity_id,link_type,target_id,target_url,
                join_confidence,relationship,evidence->>'via_award' FROM opportunity_links
                WHERE opportunity_id=%s ORDER BY link_type,target_id""",(opportunity_id,)).fetchall()
        fields=('opportunity_id','link_type','target_id','target_url','join_confidence','relationship','via_award')
        edges=[]
        for row in rows:
            edge=dict(zip(fields,row))
            edge['source_id']=opportunity_id if edge['link_type']=='award' else edge['via_award']
            edges.append(edge)
        return {'opportunity_id':opportunity_id,'edges':edges,'feed_generated_at':exists[0].isoformat()}



    def gap(self, topic, window_months=12):
        from .aggregation import aggregate
        topic=topic_value(topic)
        if type(window_months) is not int or not 1<=window_months<=120:
            raise QueryError('window_months must be an integer from 1 to 120')
        fields=('opportunity_id','title_normalized',*SCORES,'methodology_version','score_evidence',
                'linked_awards','linked_papers','source_refs','feed_generated_at')
        with read_connection() as conn:
            rows=conn.execute("""SELECT opportunity_id,title_normalized,growth_score,momentum_score,
                novelty_score,gap_score,methodology_version,record->'score_evidence',
                record->'linked_awards',record->'linked_papers',source_refs,feed_generated_at
                FROM opportunities WHERE """+VECTOR+" @@ plainto_tsquery('english',%s) ORDER BY opportunity_id",(topic,)).fetchall()
            feed=conn.execute("SELECT max(feed_generated_at) FROM feed_runs WHERE status='success'").fetchone()[0]
        result=aggregate([dict(zip(fields,row)) for row in rows],topic,window_months)
        result['feed_generated_at']=feed.isoformat() if feed else None
        return result



    def search_free(self,topic,sponsor=None,deadline_before=None,deadline_after=None,limit=10,as_of=None):
        from .snapshots import search_free
        topic,sponsor,before,after,_,limit=search_values(topic,sponsor,deadline_before,deadline_after,None,limit)
        with read_connection() as conn:
            return search_free(conn,topic,sponsor,before,after,limit,as_of)


def identifier_value(value):
    if not isinstance(value,str) or not value.strip() or len(value)>200:
        raise QueryError('opportunity_id must be a nonempty string of at most 200 characters')
    return value.strip()
