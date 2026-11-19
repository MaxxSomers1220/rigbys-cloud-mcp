"""Verify a one-time Gumroad pass without recording license or provider payloads.

Contract: https://gumroad.com/help/article/76-license-keys
The documented license response has receipt fields, not a mandatory payment-state
field. Gumroad's optional ``test`` flag is present for creator test purchases;
ordinary purchases may omit it. Synthetic test fixtures never establish a sale.
"""
from dataclasses import dataclass
import hashlib
import os

import httpx

MCP_PASS_MIN_PRICE_USD = 1


class VerificationError(ValueError):
    """A license or its purchase does not qualify for this pass."""

    def __init__(self):
        super().__init__("That license key or purchase isn't valid for this pass.")


class VerificationUnavailable(RuntimeError):
    """Verification cannot safely finish; no key may be issued."""

    def __init__(self):
        super().__init__('License verification is unavailable. Please try again later.')


@dataclass(frozen=True)
class VerifiedPurchase:
    sale_id: str
    email: str
    license_hash: str


def _text(value, limit):
    if not isinstance(value, str):
        raise VerificationError()
    value = value.strip()
    if not value or len(value) > limit or any(ord(char) < 32 for char in value):
        raise VerificationError()
    return value


class GumroadVerifier:
    endpoint = 'https://api.gumroad.com/v2/licenses/verify'
    timeout = 15.0

    def __init__(self, client=None, product_id=None):
        self.client = client if client is not None else httpx.Client(
            timeout=self.timeout, follow_redirects=False)
        self.product_id = (os.environ.get('GUMROAD_PRODUCT_ID', '')
                           if product_id is None else product_id)

    def verify(self, license_key, email):
        # No guessed product IDs, fixture mode, or fallback entitlement.
        if not isinstance(self.product_id, str) or not self.product_id.strip():
            raise VerificationUnavailable()
        product_id = self.product_id.strip()
        license_key = _text(license_key, 512)
        email = _text(email, 320).casefold()
        if '@' not in email:
            raise VerificationError()
        canonical_license = license_key.upper()
        try:
            response = self.client.post(
                self.endpoint,
                data={'product_id': product_id, 'license_key': license_key,
                      'increment_uses_count': 'false'},
                timeout=self.timeout, follow_redirects=False,
            )
        except httpx.HTTPError:
            raise VerificationUnavailable() from None
        # Disabled, missing, and wrong-product licenses are normally 404.
        if response.status_code in (400, 404):
            raise VerificationError()
        if response.status_code != 200:
            raise VerificationUnavailable()
        try:
            result = response.json()
        except (ValueError, UnicodeError):
            raise VerificationUnavailable() from None
        if not isinstance(result, dict):
            raise VerificationUnavailable()
        if result.get('success') is False:
            raise VerificationError()
        if result.get('success') is not True:
            raise VerificationUnavailable()
        purchase = result.get('purchase')
        # Imported customers can have a valid license without a paid purchase.
        if not isinstance(purchase, dict):
            raise VerificationError()
        if purchase.get('product_id') != product_id:
            raise VerificationError()
        purchase_email = _text(purchase.get('email'), 320).casefold()
        if purchase_email != email:
            raise VerificationError()
        sale_id = _text(purchase.get('sale_id'), 256)
        if canonical_license in sale_id.upper():
            raise VerificationError()
        if 'license_key' in purchase:
            provider_license = _text(purchase['license_key'], 512).upper()
            if provider_license != canonical_license:
                raise VerificationError()
        # Gumroad's pay-what-you-want receipt price excludes sales tax.
        price = purchase.get('price')
        if type(price) is not int or price < MCP_PASS_MIN_PRICE_USD * 100:
            raise VerificationError()
        if not isinstance(purchase.get('currency'), str) or purchase['currency'].casefold() != 'usd':
            raise VerificationError()
        if type(purchase.get('quantity')) is not int or purchase['quantity'] != 1:
            raise VerificationError()
        for flag in ('refunded', 'disputed', 'chargebacked'):
            if purchase.get(flag) is not False:
                raise VerificationError()
        if 'dispute_won' in purchase and type(purchase['dispute_won']) is not bool:
            raise VerificationError()
        # Optional true-only flags are omitted from ordinary Gumroad receipts.
        for flag in ('test', 'is_preorder_authorization', 'is_recurring_charge'):
            if flag in purchase and purchase[flag] is not False:
                raise VerificationError()
        for field in ('subscription_id', 'recurrence'):
            if purchase.get(field) not in (None, ''):
                raise VerificationError()
        for field in ('subscription_ended_at', 'subscription_cancelled_at', 'subscription_failed_at'):
            if purchase.get(field) is not None:
                raise VerificationError()
        return VerifiedPurchase(
            sale_id=sale_id, email=purchase_email,
            license_hash=hashlib.sha256(canonical_license.encode('utf-8')).hexdigest(),
        )
