"""Atomic pass issuance; raw credentials exist only during verification/display."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import os
import re
import secrets

import psycopg
from .gumroad import VerificationError, VerificationUnavailable


class KeyErrorResponse(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message
        super().__init__(message)


@dataclass(frozen=True, repr=False)
class IssuedKey:
    raw_key: str
    expires_at: datetime


def utcnow():
    return datetime.now(timezone.utc)


def normalize_email(value):
    if not isinstance(value,str):
        raise KeyErrorResponse(400,'Enter a valid email address.')
    value=value.strip().casefold()
    if len(value)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value):
        raise KeyErrorResponse(400,'Enter a valid email address.')
    return value


def generate_key():
    return 'rgby_live_'+secrets.token_urlsafe(32)


def redeem(license_key,email,verifier):
    email=normalize_email(email)
    if not isinstance(license_key,str) or not license_key.strip() or len(license_key)>512:
        raise KeyErrorResponse(400,'Enter a valid license key.')
    try:
        purchase=verifier.verify(license_key.strip(),email)
    except VerificationError:
        raise KeyErrorResponse(400,"That license key or purchase isn't valid for this pass.") from None
    except VerificationUnavailable:
        raise KeyErrorResponse(503,'License verification is unavailable. Please try again later.') from None
    # Product/price/email/receipt checks are the verifier's responsibility. Never
    # persist its raw request/response or return that payload to the browser.
    reference='gumroad:'+purchase.sale_id
    now=utcnow()
    raw=generate_key()
    digest=hashlib.sha256(raw.encode()).hexdigest()
    expires=now+timedelta(days=90)
    try:
        with psycopg.connect(os.environ['DATABASE_URL'],autocommit=True) as conn:
            with conn.transaction():
                conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',(reference,))
                prior=conn.execute('''SELECT 1 FROM redemptions
                    WHERE license_key_hash=%s OR gumroad_sale_ref=%s''',
                    (purchase.license_hash,reference)).fetchone()
                if prior:
                    raise KeyErrorResponse(409,'That license key has already been redeemed. Use the key-rotation option if you need a replacement.')
                conn.execute('''INSERT INTO api_keys(key_hash,key_prefix,tier,email,expires_at,created_at)
                    VALUES (%s,%s,'paid',%s,%s,%s)''',(digest,raw[:12],email,expires,now))
                conn.execute('''INSERT INTO redemptions(license_key_hash,api_key_hash,redeemed_at,gumroad_sale_ref)
                    VALUES (%s,%s,%s,%s)''',(purchase.license_hash,digest,now,reference))
    except psycopg.errors.UniqueViolation as exc:
        if exc.diag.constraint_name in {'redemptions_pkey','redemptions_verified_sale_ref_unique_idx'}:
            raise KeyErrorResponse(409,'That license key has already been redeemed.') from None
        raise KeyErrorResponse(503,'Unable to issue a key. Please try again later.') from None
    except (psycopg.Error,KeyError):
        raise KeyErrorResponse(503,'Key service is temporarily unavailable.') from None
    return IssuedKey(raw,expires)


def rotate(license_key,email,verifier):
    """Replace a verified paid key without extending access or resetting quota.

    A generation is observed before the provider request. Concurrent rotations
    verifying that same generation cannot both issue a replacement. No database
    lock is held while Gumroad is contacted, and no current key is required for
    license-and-purchase-email recovery.
    """
    email=normalize_email(email)
    if not isinstance(license_key,str) or not license_key.strip() or len(license_key)>512:
        raise KeyErrorResponse(400,'Enter a valid license key.')
    license_key=license_key.strip()
    license_hash=hashlib.sha256(license_key.upper().encode('utf-8')).hexdigest()
    try:
        with psycopg.connect(os.environ['DATABASE_URL'],autocommit=True) as conn:
            prior=conn.execute('SELECT api_key_hash FROM redemptions WHERE license_key_hash=%s',
                               (license_hash,)).fetchone()
    except (psycopg.Error,KeyError):
        raise KeyErrorResponse(503,'Key service is temporarily unavailable.') from None
    if prior is None:
        raise KeyErrorResponse(400,'That pass has not been redeemed or cannot be rotated.')
    expected_hash=prior[0]
    try:
        purchase=verifier.verify(license_key,email)
    except VerificationError:
        raise KeyErrorResponse(400,"That license key or purchase isn't valid for this pass.") from None
    except VerificationUnavailable:
        raise KeyErrorResponse(503,'License verification is unavailable. Please try again later.') from None
    if purchase.license_hash!=license_hash or purchase.email!=email:
        raise KeyErrorResponse(400,"That license key or purchase doesn't match this pass.")
    reference='gumroad:'+purchase.sale_id
    try:
        with psycopg.connect(os.environ['DATABASE_URL'],autocommit=True) as conn:
            with conn.transaction():
                redemption=conn.execute('''SELECT api_key_hash,redeemed_at,gumroad_sale_ref
                    FROM redemptions WHERE license_key_hash=%s FOR UPDATE''',(license_hash,)).fetchone()
                if redemption is None or redemption[0]!=expected_hash:
                    raise KeyErrorResponse(409,'This pass changed during verification. Please retry rotation.')
                old_hash,redeemed,sale_reference=redemption
                row=conn.execute('''SELECT email,expires_at,revoked_at,tier
                    FROM api_keys WHERE key_hash=%s FOR UPDATE''',(old_hash,)).fetchone()
                if row is None:
                    raise KeyErrorResponse(401,'Key is not active.')
                stored_email,expires,revoked,tier=row
                if stored_email!=email or sale_reference!=reference or tier!='paid':
                    raise KeyErrorResponse(400,"That license key or purchase doesn't match this pass.")
                now=utcnow()
                if revoked is not None:
                    raise KeyErrorResponse(401,'Key is revoked and cannot be rotated.')
                if expires is None or redeemed is None or redeemed>now:
                    raise KeyErrorResponse(401,'Key is not active.')
                expires=min(expires,redeemed+timedelta(days=90))
                if expires<=now:
                    raise KeyErrorResponse(401,'Key expired — renew at mcp.rigbyscloud.com/redeem')
                raw=generate_key()
                digest=hashlib.sha256(raw.encode()).hexdigest()
                conn.execute('''INSERT INTO api_keys(key_hash,key_prefix,tier,email,expires_at,created_at)
                    VALUES (%s,%s,'paid',%s,%s,%s)''',(digest,raw[:12],email,expires,now))
                conn.execute('''UPDATE api_keys SET revoked_at=%s,rotated_at=%s WHERE key_hash=%s''',
                             (now,now,old_hash))
                # FOR UPDATE on the old key waits for auth's FOR SHARE lock. All
                # successful in-flight calls finish before their usage is copied.
                conn.execute('''INSERT INTO rate_limit_counters(key_hash,day,calls)
                    SELECT %s,day,calls FROM rate_limit_counters WHERE key_hash=%s''',
                    (digest,old_hash))
                conn.execute('UPDATE redemptions SET api_key_hash=%s WHERE license_key_hash=%s',
                             (digest,license_hash))
    except (psycopg.Error,KeyError):
        raise KeyErrorResponse(503,'Unable to rotate a key. Please try again later.') from None
    return IssuedKey(raw,expires)
