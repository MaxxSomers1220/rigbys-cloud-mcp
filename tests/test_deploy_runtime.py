"""Production startup/proxy checks without test keys or license submissions."""
from html.parser import HTMLParser
import socket
import threading
import time

import httpx
import pytest
import uvicorn

from rigbys_mcp import app as application
from test_database import database  # noqa: F401 -- isolated database fixture


@pytest.mark.parametrize('settings,expected',[
    ({},('127.0.0.1',8000,'127.0.0.1')),
    ({'HOST':'0.0.0.0','PORT':'8123','FORWARDED_ALLOW_IPS':'*'},('0.0.0.0',8123,'*')),
    ({'HOST':'0.0.0.0','FORWARDED_ALLOW_IPS':'10.0.0.0/8'},('0.0.0.0',8000,'10.0.0.0/8')),
])
def test_startup_explicit_bind_and_proxy_trust(monkeypatch,settings,expected):
    for key in ('HOST','PORT','FORWARDED_ALLOW_IPS'):
        monkeypatch.delenv(key,raising=False)
    for key,value in settings.items():monkeypatch.setenv(key,value)
    calls=[]
    monkeypatch.setattr(application.uvicorn,'run',lambda *args,**kwargs:calls.append((args,kwargs)))
    application.main()
    args,options=calls[0]
    assert args==('rigbys_mcp.app:create_app',)
    assert (options['host'],options['port'],options['forwarded_allow_ips'])==expected
    assert options['factory'] and options['proxy_headers']
    assert options['access_log'] is False


class CSRF(HTMLParser):
    def __init__(self):super().__init__();self.token=None
    def handle_starttag(self,tag,attributes):
        attributes=dict(attributes)
        if tag=='input' and attributes.get('name')=='csrf_token':self.token=attributes.get('value')


def test_trusted_https_proxy_sets_secure_cookie_and_accepts_origin(database,monkeypatch):
    monkeypatch.setenv('DATABASE_URL',database.info.dsn)
    monkeypatch.delenv('GUMROAD_PRODUCT_ID',raising=False)
    app=application.create_app()
    class NeverVerify:
        def verify(self,*args):pytest.fail('An empty form must not contact Gumroad')
    app.state.license_verifier=NeverVerify()
    listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(32)
    server=uvicorn.Server(uvicorn.Config(app,proxy_headers=True,forwarded_allow_ips='127.0.0.1',
                                       access_log=False,log_level='critical',lifespan='on'))
    thread=threading.Thread(target=server.run,kwargs={'sockets':[listener]},daemon=True)
    thread.start()
    deadline=time.monotonic()+15
    while not server.started and thread.is_alive() and time.monotonic()<deadline:
        time.sleep(0.01)
    assert server.started
    try:
        url='http://127.0.0.1:'+str(listener.getsockname()[1])
        headers={'Host':'mcp.rigbyscloud.com','X-Forwarded-Proto':'https'}
        with httpx.Client(base_url=url,headers=headers,timeout=15) as client:
            response=client.get('/redeem')
            assert response.status_code==200
            assert '; Secure' in response.headers['set-cookie']
            parsed=CSRF();parsed.feed(response.text);assert parsed.token
            # The connection is local HTTP, so send the browser's HTTPS cookie
            # explicitly while reproducing the trusted proxy's forwarded scheme.
            invalid=client.post('/redeem',data={'csrf_token':parsed.token,'license_key':'','email':''},
                headers={'Origin':'https://mcp.rigbyscloud.com',
                         'Cookie':'rigbys_redeem_csrf='+parsed.token})
            assert invalid.status_code==400
            assert 'valid email' in invalid.text.lower()
            assert 'reload the access page' not in invalid.text.lower()
            assert database.execute('SELECT count(*) FROM api_keys').fetchone()[0]==0
            assert database.execute('SELECT count(*) FROM redemptions').fetchone()[0]==0
    finally:
        server.should_exit=True;thread.join(timeout=15);listener.close()
        assert not thread.is_alive()
