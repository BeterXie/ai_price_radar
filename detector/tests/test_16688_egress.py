import contextlib
import io
import json
import socket
import ssl
import time

import pytest
from price_radar_http import PinnedHTTPSClient
from price_radar_http import egress, pacing
from price_radar_http.pinned import PinnedResponse


def test_default_client_requires_modern_tls():
    client=PinnedHTTPSClient()
    assert client.ssl_context.minimum_version>=ssl.TLSVersion.TLSv1_2
    assert client.ssl_context.verify_mode==ssl.CERT_REQUIRED and client.ssl_context.check_hostname


@pytest.fixture
def proxy(tmp_path, monkeypatch):
    path=tmp_path/'proxy.key'
    path.write_text(json.dumps({'proxy_password':'p'*40,'controller_token':'t'*40}))
    monkeypatch.setenv('COLLECTOR_16688_PROXY_KEY_FILE',str(path))
    monkeypatch.setenv('COLLECTOR_RATE_DIR',str(tmp_path))
    return egress.settings_for('www.16688.com.cn')


def test_connect_tunnels_to_pinned_numeric_ip_and_verifies_original_tls_name(proxy):
    calls=[];sent=[];tls_names=[]
    responses=iter([b'HTTP/1.1 200 Connection established\r\n\r\n',
                    b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}'])
    class Socket:
        def settimeout(self,*_):pass
        def sendall(self,data):sent.append(data)
        def makefile(self,*_,**__):return io.BytesIO(next(responses))
        def close(self):pass
    class TLS:
        def wrap_socket(self,raw,server_hostname):tls_names.append(server_hostname);return raw
    client=PinnedHTTPSClient(
        resolver=lambda *_,**__: [(socket.AF_INET,socket.SOCK_STREAM,6,'',('93.184.216.34',443))],
        connector=lambda address,**_: calls.append(address) or Socket(),ssl_context=TLS())
    result=client._request_direct('https://www.16688.com.cn/shopApi/shop/detail',method='GET',accept='application/json')
    assert result.status==200
    assert calls==[(egress.PROXY_ADDRESS,egress.PROXY_PORT)]
    assert sent[0].startswith(b'CONNECT 93.184.216.34:443 HTTP/')
    assert b'Proxy-Authorization: Basic ' in sent[0]
    assert b'Proxy-Authorization' not in sent[1] and b't'*40 not in b''.join(sent)
    assert tls_names==['www.16688.com.cn']


def test_proxy_does_not_relax_public_dns_or_forward_platform_credentials(proxy):
    calls=[]
    client=PinnedHTTPSClient(resolver=lambda *_,**__:[(socket.AF_INET,socket.SOCK_STREAM,6,'',('169.254.169.254',443))],
                            connector=lambda *_,**__: calls.append(True))
    with pytest.raises(ValueError,match='non-public'):
        client._request_direct('https://www.16688.com.cn/',method='GET',accept='application/json')
    with pytest.raises(ValueError,match='credential headers'):
        client.post_json('https://www.16688.com.cn/',{},headers={'X-Api-Key':'never-forward'})
    assert not calls
    assert egress.settings_for('www.kmdian.com') is None
    assert egress.settings_for('16688.com.cn.attacker.example') is None


def install_budget(monkeypatch):
    statuses=[]
    @contextlib.contextmanager
    def budget(*_,**__):
        def received(status,allow_failover=False):
            statuses.append(status)
            if status in (0,403,429,520) and not (status==520 and allow_failover):
                raise pacing.OriginCoolingDown('cooling down')
        yield received
    monkeypatch.setattr(pacing,'origin_budget',budget)
    return statuses


@pytest.mark.parametrize('results,rotations,blocked', [([520,200],1,False),([520,520,520],2,True),([403],0,True),([429],0,True)])
def test_failover_is_bounded_and_rate_limits_do_not_rotate(proxy,monkeypatch,results,rotations,blocked):
    statuses=install_budget(monkeypatch);switches=[]
    def rotate(*args,allow_switch=True):
        if allow_switch:switches.append(True)
        return allow_switch
    monkeypatch.setattr(egress,'rotate',rotate)
    responses=iter(results)
    client=PinnedHTTPSClient()
    def request(*_,on_status,**__):
        status=next(responses);on_status(status);return PinnedResponse(status,{},b'{}')
    monkeypatch.setattr(client,'_request_direct',request)
    if blocked:
        with pytest.raises(pacing.OriginCoolingDown):client.get('https://www.16688.com.cn/',accept='application/json')
    else:
        assert client.get('https://www.16688.com.cn/',accept='application/json').status==200
    assert len(switches)==rotations


def test_certificate_failure_never_rotates_or_disables_verification(proxy,monkeypatch):
    install_budget(monkeypatch)
    monkeypatch.setattr(egress,'rotate',lambda *args: pytest.fail('certificate failure must stay fatal'))
    client=PinnedHTTPSClient()
    def bad_tls(*_,**__):raise ssl.SSLCertVerificationError('untrusted certificate')
    monkeypatch.setattr(client,'_request_direct',bad_tls)
    with pytest.raises(ssl.SSLCertVerificationError):client.get('https://16688.com.cn/',accept='text/plain')


def test_bad_source_body_does_not_quarantine_a_healthy_proxy(proxy,monkeypatch):
    install_budget(monkeypatch)
    monkeypatch.setattr(egress,'rotate',lambda *args,**kwargs:pytest.fail('body failure is not a proxy connection error'))
    client=PinnedHTTPSClient()
    def truncated(*args,**kwargs):raise http.client.IncompleteRead(b'partial',100)
    import http.client
    monkeypatch.setattr(client,'_request_direct',truncated)
    with pytest.raises(http.client.IncompleteRead):client.get('https://www.16688.com.cn/',accept='text/plain')


def test_slow_connect_headers_are_cut_off_at_absolute_deadline(proxy):
    import threading
    client,server=socket.socketpair();done=threading.Event()
    def slow_proxy():
        try:
            server.recv(4096)
            for character in b'HTTP/1.1 200 Connection established\r\n\r\n':
                if done.wait(.03):break
                server.sendall(bytes([character]))
        except OSError:pass
        finally:server.close()
    thread=threading.Thread(target=slow_proxy,daemon=True);thread.start()
    start=time.monotonic()
    try:
        with pytest.raises(TimeoutError):
            egress.connect_tunnel(proxy,lambda *args,**kwargs:client,'93.184.216.34',443,
                                  'www.16688.com.cn',start+.12,5)
        assert time.monotonic()-start<.8
    finally:
        done.set();client.close();thread.join(timeout=1)
