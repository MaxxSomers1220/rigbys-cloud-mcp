"""Synthetic provider-contract tests only: no real product, buyer, or sale calls.

The successful response simulates an ordinary paid purchase. A real Gumroad test
purchase has ``test: true`` and must never authorize a production paid pass.
"""
from dataclasses import asdict
import hashlib
import json
import math
import os
import secrets
from urllib.parse import parse_qs

import httpx
import pytest

from rigbys_mcp.gumroad import (
    GumroadVerifier, VerifiedPurchase, VerificationError, VerificationUnavailable,
)


@pytest.fixture
def provider(monkeypatch):
    # Runtime generated and placed in the test environment; never a real license.
    license_key = '-'.join(secrets.token_hex(4).upper() for _ in range(4))
    monkeypatch.setenv('RIGBYS_TEST_LICENSE_KEY', license_key)
    monkeypatch.setenv('GUMROAD_PRODUCT_ID', 'synthetic-product-not-a-real-product==')
    payload = {
        'success': True,
        'uses': 0,
        'purchase': {
            'product_id': os.environ['GUMROAD_PRODUCT_ID'],
            'email': 'synthetic-buyer@example.invalid',
            'sale_id': 'synthetic-sale-not-a-real-sale',
            'license_key': os.environ['RIGBYS_TEST_LICENSE_KEY'],
            'price': 100,
            'currency': 'usd',
            'quantity': 1,
            'refunded': False,
            'disputed': False,
            'dispute_won': False,
            'chargebacked': False,
            'test': False,
            'subscription_id': None,
            'recurrence': None,
            'subscription_ended_at': None,
            'subscription_cancelled_at': None,
            'subscription_failed_at': None,
        },
    }
    return license_key, payload


def verifier_for(payload, *, status=200, handler=None, follow_redirects=False):
    if handler is None:
        handler = lambda request: httpx.Response(status, json=payload)
    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=follow_redirects)
    return GumroadVerifier(client=client)


def test_exact_fixed_https_form_and_only_redacted_verified_fields(provider):
    key, payload = provider
    requests = []
    def handle(request):
        requests.append(request)
        assert request.method == 'POST'
        assert str(request.url) == 'https://api.gumroad.com/v2/licenses/verify'
        assert request.headers['content-type'].startswith('application/x-www-form-urlencoded')
        assert 'authorization' not in request.headers
        assert parse_qs(request.content.decode()) == {
            'product_id': [payload['purchase']['product_id']],
            'license_key': [key], 'increment_uses_count': ['false'],
        }
        assert request.extensions.get('timeout')
        assert all(value is not None and math.isfinite(value) and value > 0
                   for value in request.extensions['timeout'].values())
        return httpx.Response(200, json=payload)
    result = verifier_for(payload, handler=handle).verify(key, payload['purchase']['email'])
    assert isinstance(result, VerifiedPurchase)
    assert asdict(result) == {
        'sale_id': payload['purchase']['sale_id'],
        'email': payload['purchase']['email'],
        'license_hash': hashlib.sha256(key.encode()).hexdigest(),
    }
    assert len(requests) == 1
    assert key not in repr(result)


def test_normal_license_response_can_omit_optional_test_flag(provider):
    key, payload = provider
    del payload['purchase']['test']
    assert verifier_for(payload).verify(key, payload['purchase']['email']).sale_id == payload['purchase']['sale_id']


def test_provider_license_may_be_omitted_without_inventing_a_required_field(provider):
    key, payload = provider
    del payload['purchase']['license_key']
    assert verifier_for(payload).verify(key, payload['purchase']['email']).license_hash == hashlib.sha256(key.encode()).hexdigest()


def test_email_and_license_canonicalization_prevents_duplicate_hashes(provider):
    key, payload = provider
    result = verifier_for(payload).verify('  ' + key.lower() + '  ', '  SYNTHETIC-BUYER@EXAMPLE.INVALID  ')
    assert result.email == 'synthetic-buyer@example.invalid'
    assert result.license_hash == hashlib.sha256(key.encode()).hexdigest()


@pytest.mark.parametrize('price', [100, 101, 9900])
def test_paid_pass_accepts_the_minimum_and_higher_payments(provider, price):
    key, payload = provider
    purchase = payload['purchase']
    purchase['price'] = price
    assert verifier_for(payload).verify(key, purchase['email']).sale_id == purchase['sale_id']


@pytest.mark.parametrize('field,value', [
    ('product_id', 'synthetic-wrong-product'),
    ('email', 'synthetic-other-buyer@example.invalid'),
    ('sale_id', ''), ('sale_id', None), ('sale_id', 12),
    ('license_key', 'synthetic-mismatched-license'),
    ('price', 0), ('price', 99), ('price', 100.0), ('price', '100'), ('price', True),
    ('currency', 'eur'), ('currency', None),
    ('quantity', 2), ('quantity', 0), ('quantity', True), ('quantity', '1'),
    ('refunded', True), ('refunded', None), ('refunded', 'false'),
    ('disputed', True), ('disputed', None), ('disputed', 'false'),
    ('chargebacked', True), ('chargebacked', None), ('chargebacked', 'false'),
    ('test', True), ('test', 'false'), ('test', None),
    ('is_preorder_authorization', True),
    ('is_recurring_charge', True),
    ('subscription_id', 'synthetic-subscription'), ('recurrence', 'monthly'),
    ('subscription_ended_at', '2026-01-01T00:00:00Z'),
    ('subscription_cancelled_at', '2026-01-01T00:00:00Z'),
    ('subscription_failed_at', '2026-01-01T00:00:00Z'),
])
def test_ineligible_or_malformed_purchase_rejected(provider, field, value):
    key, payload = provider
    payload['purchase'][field] = value
    with pytest.raises((VerificationError, VerificationUnavailable)):
        verifier_for(payload).verify(key, 'synthetic-buyer@example.invalid')


def test_sale_reference_cannot_be_the_raw_license(provider):
    key, payload = provider
    payload['purchase']['sale_id'] = key
    with pytest.raises((VerificationError, VerificationUnavailable)):
        verifier_for(payload).verify(key, payload['purchase']['email'])


@pytest.mark.parametrize('field', ['product_id', 'email', 'sale_id', 'price', 'currency', 'quantity', 'refunded', 'disputed', 'chargebacked'])
def test_missing_documented_critical_field_fails_closed(provider, field):
    key, payload = provider
    del payload['purchase'][field]
    with pytest.raises((VerificationError, VerificationUnavailable)):
        verifier_for(payload).verify(key, 'synthetic-buyer@example.invalid')


def test_won_dispute_does_not_override_a_disputed_purchase(provider):
    key, payload = provider
    payload['purchase'].update(disputed=True, dispute_won=True)
    with pytest.raises(VerificationError):
        verifier_for(payload).verify(key, payload['purchase']['email'])


@pytest.mark.parametrize('success', [False, 'true', 1, None])
def test_success_must_be_explicit_boolean_true(provider, success):
    key, payload = provider
    payload['success'] = success
    with pytest.raises((VerificationError, VerificationUnavailable)):
        verifier_for(payload).verify(key, payload['purchase']['email'])


def test_imported_customer_without_purchase_is_not_a_paid_sale(provider):
    key, payload = provider
    payload = {'success': True, 'uses': 0, 'imported_customer': {'email': payload['purchase']['email']}}
    with pytest.raises((VerificationError, VerificationUnavailable)):
        verifier_for(payload).verify(key, 'synthetic-buyer@example.invalid')


@pytest.mark.parametrize('status', [400, 404])
def test_invalid_or_disabled_license_uses_plain_invalid_error(provider, status):
    key, payload = provider
    response = {'success': False, 'message': key + ' ' + payload['purchase']['email']}
    with pytest.raises(VerificationError) as caught:
        verifier_for(response, status=status).verify(key, payload['purchase']['email'])
    assert key not in str(caught.value)
    assert payload['purchase']['email'] not in str(caught.value)


@pytest.mark.parametrize('status', [401, 403, 429, 500, 503])
def test_provider_failure_is_unavailable_and_redacted(provider, status):
    key, payload = provider
    response = {'success': False, 'message': key + ' ' + payload['purchase']['email']}
    with pytest.raises(VerificationUnavailable) as caught:
        verifier_for(response, status=status).verify(key, payload['purchase']['email'])
    assert key not in str(caught.value)
    assert payload['purchase']['email'] not in str(caught.value)


def test_redirects_are_not_followed_even_with_injected_following_client(provider):
    key, payload = provider
    calls = []
    def handle(request):
        calls.append(request)
        return httpx.Response(307, headers={'location': 'https://synthetic-untrusted.example.invalid/capture'})
    with pytest.raises(VerificationUnavailable):
        verifier_for(payload, handler=handle, follow_redirects=True).verify(key, payload['purchase']['email'])
    assert len(calls) == 1
    assert calls[0].url.host == 'api.gumroad.com'


def test_network_exception_message_is_not_exposed(provider):
    key, payload = provider
    def handle(request):
        raise httpx.ConnectError(key + ' ' + payload['purchase']['email'], request=request)
    with pytest.raises(VerificationUnavailable) as caught:
        verifier_for(payload, handler=handle).verify(key, payload['purchase']['email'])
    assert key not in str(caught.value)
    assert payload['purchase']['email'] not in str(caught.value)


@pytest.mark.parametrize('body', ['not-json', 'null', '[]', '{}', '{"success":true,"purchase":[]}'])
def test_malformed_provider_response_fails_closed(provider, body):
    key, payload = provider
    def handle(request):
        return httpx.Response(200, text=body)
    with pytest.raises((VerificationError, VerificationUnavailable)):
        verifier_for(payload, handler=handle).verify(key, payload['purchase']['email'])


def test_missing_product_configuration_never_sends_a_request(provider, monkeypatch):
    key, payload = provider
    monkeypatch.delenv('GUMROAD_PRODUCT_ID')
    calls = []
    def handle(request):
        calls.append(request)
        return httpx.Response(200, json=payload)
    with pytest.raises(VerificationUnavailable):
        verifier_for(payload, handler=handle).verify(key, payload['purchase']['email'])
    assert calls == []


def test_sale_reference_cannot_embed_license_anywhere(provider):
    key, payload = provider
    payload['purchase']['sale_id'] = 'synthetic-prefix/' + key.lower() + '/synthetic-suffix'
    with pytest.raises(VerificationError) as caught:
        verifier_for(payload).verify(key, payload['purchase']['email'])
    assert key.casefold() not in str(caught.value).casefold()
    assert payload['purchase']['sale_id'] not in str(caught.value)
