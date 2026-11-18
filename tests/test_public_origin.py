"""Public-origin security across HTTPS termination and untrusted HTTP ingress."""
from html.parser import HTMLParser

from fastapi.testclient import TestClient
import pytest

from rigbys_mcp.app import create_app


PUBLIC_ORIGIN = 'https://mcp.rigbyscloud.com'


class FormToken(HTMLParser):
    def __init__(self):
        super().__init__()
        self.token = None

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        if tag == 'input' and attributes.get('name') == 'csrf_token':
            self.token = attributes['value']


@pytest.fixture
def public_app(monkeypatch):
    # Empty-field validation must finish before any database/provider operation.
    monkeypatch.setenv('DATABASE_URL', 'postgresql://unused.invalid/unused')
    monkeypatch.setenv('RIGBYS_PUBLIC_ORIGIN', PUBLIC_ORIGIN)
    app = create_app()

    class NeverVerify:
        def verify(self, *args):
            pytest.fail('Origin and empty-form checks must not contact Gumroad')

    app.state.license_verifier = NeverVerify()
    return app


def empty_form(client, **headers):
    response = client.get('/redeem', headers=headers)
    parser = FormToken()
    parser.feed(response.text)
    assert response.status_code == 200 and parser.token
    return response, {'csrf_token': parser.token, 'license_key': '', 'email': ''}


@pytest.mark.parametrize('forwarded_proto', [None, 'http', 'https'])
def test_public_https_origin_over_http_ingress(public_app, forwarded_proto):
    # TestClient has no proxy middleware: ASGI scheme remains the HTTP ingress
    # scheme, regardless of the untrusted X-Forwarded-Proto header.
    with TestClient(public_app, base_url='http://internal-ingress.invalid') as client:
        forwarded = {} if forwarded_proto is None else {'X-Forwarded-Proto': forwarded_proto}
        response, fields = empty_form(client, **forwarded)
        assert '; Secure' in response.headers['set-cookie']
        assert '; HttpOnly' in response.headers['set-cookie']
        assert 'SameSite=strict' in response.headers['set-cookie']
        headers = {**forwarded, 'Origin': PUBLIC_ORIGIN,
                   'Cookie': 'rigbys_redeem_csrf=' + fields['csrf_token']}
        result = client.post('/redeem', data=fields, headers=headers)
        assert result.status_code == 400
        assert 'valid email' in result.text.lower()
        assert 'reload the access page' not in result.text.lower()


@pytest.mark.parametrize('spoofed_origin', [
    'http://mcp.rigbyscloud.com',
    'http://internal-ingress.invalid',
    'https://mcp.rigbyscloud.com.attacker.invalid',
    'https://attacker.invalid',
    'null',
])
def test_public_origin_rejects_spoofed_origin(public_app, spoofed_origin):
    with TestClient(public_app, base_url='http://internal-ingress.invalid') as client:
        _, fields = empty_form(client)
        result = client.post('/redeem', data=fields, headers={
            'Origin': spoofed_origin,
            'X-Forwarded-Proto': 'https',
            'X-Forwarded-Host': 'attacker.invalid',
            'Cookie': 'rigbys_redeem_csrf=' + fields['csrf_token'],
        })
        assert result.status_code == 403
        assert 'reload the access page' in result.text.lower()


@pytest.mark.parametrize('invalid_origin', [
    '', 'http://mcp.rigbyscloud.com', 'https://',
    'https://user:secret@mcp.rigbyscloud.com',
    'https://mcp.rigbyscloud.com/redeem',
    'https://mcp.rigbyscloud.com?key=secret',
    'https://mcp.rigbyscloud.com#secret',
    'https://mcp.rigbyscloud.com?', 'https://mcp.rigbyscloud.com#',
    'https://mcp.rigbyscloud.com:invalid',
    'https://mcp.rigbyscloud.com:65536',
    ' https://mcp.rigbyscloud.com',
    'https://mcp.rigbyscloud.com\n',
    'https://mcp.rigbyscloud.com\\attacker.invalid',
    'https://bad host.invalid', 'https://-bad.invalid',
])
def test_invalid_public_origin_fails_startup_with_plain_error(monkeypatch, invalid_origin):
    monkeypatch.setenv('DATABASE_URL', 'postgresql://unused.invalid/unused')
    monkeypatch.setenv('RIGBYS_PUBLIC_ORIGIN', invalid_origin)
    with pytest.raises(RuntimeError) as raised:
        create_app()
    assert str(raised.value) == ('RIGBYS_PUBLIC_ORIGIN must be an HTTPS origin without credentials, '
                                 'a path, a query or a fragment')
    assert 'secret' not in str(raised.value)
    assert raised.value.__suppress_context__


@pytest.mark.parametrize('configured,expected', [
    (PUBLIC_ORIGIN, PUBLIC_ORIGIN),
    ('https://MCP.RIGBYSCLOUD.COM:443/', PUBLIC_ORIGIN),
    ('https://mcp.rigbyscloud.com:8443/', PUBLIC_ORIGIN + ':8443'),
    ('https://[::1]:8443/', 'https://[::1]:8443'),
])
def test_public_origin_is_validated_and_canonicalized(monkeypatch, configured, expected):
    monkeypatch.setenv('DATABASE_URL', 'postgresql://unused.invalid/unused')
    monkeypatch.setenv('RIGBYS_PUBLIC_ORIGIN', configured)
    assert create_app().state.public_origin == expected


@pytest.mark.parametrize('scheme,secure', [('http', False), ('https', True)])
def test_unconfigured_local_origin_and_cookie_behavior_remain(monkeypatch, scheme, secure):
    monkeypatch.setenv('DATABASE_URL', 'postgresql://unused.invalid/unused')
    monkeypatch.delenv('RIGBYS_PUBLIC_ORIGIN', raising=False)
    app = create_app()
    assert app.state.public_origin is None
    origin = scheme + '://local.invalid'
    with TestClient(app, base_url=origin) as client:
        response, fields = empty_form(client)
        assert ('; Secure' in response.headers['set-cookie']) is secure
        result = client.post('/redeem', data=fields, headers={'Origin': origin})
        assert result.status_code == 400
        assert 'valid email' in result.text.lower()
        _, fields = empty_form(client)
        assert client.post('/redeem', data=fields,
                           headers={'Origin': PUBLIC_ORIGIN}).status_code == 403
