"""Public source clients. Persist raw envelopes before validating/parsing them."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import time
import httpx

log = logging.getLogger(__name__)


def utcnow():
    return datetime.now(timezone.utc).isoformat()


class SourceError(RuntimeError):
    pass


class PublicClient:
    def __init__(self, raw_dir, client=None):
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.client = client or httpx.Client(timeout=90, follow_redirects=True)

    def request(self, source, method, url, **kwargs):
        for attempt in range(5):
            try:
                response = self.client.request(method, url, **kwargs)
            except httpx.TransportError:
                if attempt == 4:
                    raise SourceError(f"{source}: transport failed") from None
                time.sleep(2 ** attempt)
                continue
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == 4:
                    raise SourceError(f"{source}: HTTP {response.status_code}")
                try:
                    delay = float(response.headers.get('Retry-After', 2 ** attempt))
                except ValueError:
                    delay = 2 ** attempt
                time.sleep(max(0, delay))
                continue
            # Do not include request URLs or response bodies in errors (future credentials).
            if response.is_error:
                raise SourceError(f"{source}: HTTP {response.status_code}")
            data = response.json()
            stamp = utcnow()
            # Grants.gov returns an ephemeral web session token even for public reads.
            # Preserve all source data, but never archive credential-like fields.
            def redact(value):
                if isinstance(value, dict):
                    return {k: redact(v) for k, v in value.items()
                            if k.lower() not in {'token', 'accesskey', 'api_key', 'authorization'}}
                if isinstance(value, list):
                    return [redact(v) for v in value]
                return value
            envelope = dict(source=source, fetched_at=stamp, url=url,
                            request=redact(kwargs), response=redact(data))
            raw = json.dumps(envelope, sort_keys=True).encode()
            digest = hashlib.sha256(raw).hexdigest()
            path = self.raw_dir / source / f'{digest}.json'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            return data, {'source': source, 'url': url, 'fetched_at': stamp,
                          'raw_path': str(path), 'sha256': digest}
        raise SourceError(f'{source}: retries exhausted')


class GrantsGov:
    base = 'https://api.grants.gov/v1/api/'

    def __init__(self, http):
        self.http = http

    def detail(self, opportunity_id):
        response, ref = self.http.request('grants_gov', 'POST', self.base + 'fetchOpportunity',
                                          json={'opportunityId': int(opportunity_id)})
        if response.get('errorcode') != 0 or str(response.get('data', {}).get('id')) != str(opportunity_id):
            raise SourceError('grants_gov: invalid detail response')
        return {'record': response['data'], 'ref': ref}

    def fetch(self, limit=None, workers=4):
        hits, seen, offset = [], set(), 0
        while True:
            response, _ = self.http.request('grants_gov', 'POST', self.base + 'search2',
                json={'oppStatuses': 'posted', 'rows': 100, 'startRecordNum': offset,
                      'sortBy': 'oppNum|asc'})
            if response.get('errorcode') != 0:
                raise SourceError('grants_gov: search failed')
            data = response['data']
            page = data.get('oppHits', [])
            if not page and offset < data['hitCount']:
                raise SourceError('grants_gov: incomplete pagination')
            for hit in page:
                if hit['id'] not in seen:
                    hits.append(hit)
                    seen.add(hit['id'])
            offset += len(page)
            if offset >= data['hitCount'] or (limit and len(hits) >= limit):
                break
        if not limit and len(hits) != data['hitCount']:
            raise SourceError('grants_gov: unique count differs from search total; retry snapshot')
        selected = hits[:limit] if limit else hits
        with ThreadPoolExecutor(max_workers=workers) as pool:
            records = list(pool.map(lambda h: self.detail(h['id']), selected))
        log.info(json.dumps({'message': f'Fetched {len(records)} posted Grants.gov opportunities',
                             'level': 'info', 'source': 'grants_gov', 'count': len(records),
                             'search_total': data['hitCount'], 'fetched_at': utcnow()}))
        return records
