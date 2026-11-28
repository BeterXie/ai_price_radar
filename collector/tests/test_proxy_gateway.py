import http.client
import json
from pathlib import Path
import sys
import threading
import time

import pytest
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'collector'),str(ROOT/'shared_http')]
from proxy_gateway import Gateway,Server


@pytest.fixture
def gateway(tmp_path,monkeypatch):
    target=Gateway({'proxy_password':'p'*40,'controller_token':'t'*40},tmp_path/'quarantine.json')
    selected=['node-a'];calls=[]
    def control(method,payload=None):
        calls.append((method,payload))
        if method=='PUT':selected[0]=payload['name'];return {}
        return {'now':selected[0],'all':['node-a','node-b','node-c']}
    monkeypatch.setattr(target,'control',control)
    return target,selected,calls


def test_rotation_uses_only_fixed_selector_and_respects_quarantine(gateway):
    target,selected,calls=gateway
    assert target.rotate(True) and selected[0]=='node-b'
    assert target.rotate(True) and selected[0]=='node-c'
    assert not target.rotate(False)
    assert set(target.state())=={'node-a','node-b','node-c'}
    before=target.state()
    assert not target.rotate(True)
    assert target.state()==before
    with pytest.raises(OSError,match='quarantined'):
        target.validate_target('www.16688.store','93.184.216.34',443)


def test_source_domain_must_match_the_pinned_target(gateway,monkeypatch):
    target,_,_=gateway
    monkeypatch.setattr('proxy_gateway.PinnedHTTPSClient._public_addresses',lambda self,host:['93.184.216.34'])
    target.validate_target('www.16688.store','93.184.216.34',443)
    for host,address,port in [('www.16688.store','1.1.1.1',443),('www.16688.store','169.254.169.254',443),
                              ('attacker.example','93.184.216.34',443),('www.16688.store','93.184.216.34',80)]:
        with pytest.raises(ValueError):target.validate_target(host,address,port)


def test_gateway_rejects_unauthorized_and_arbitrary_control_paths(gateway):
    target,_,calls=gateway
    server=Server(('127.0.0.1',0),target)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        for method,path,headers,expected in [
            ('POST','/rotate',{},407),
            ('POST','/configs',{'Proxy-Authorization':target.authorization},404),
            ('GET','/proxies',{'Proxy-Authorization':target.authorization},404),
            ('GET','/health',{'Proxy-Authorization':target.authorization},200),
        ]:
            connection=http.client.HTTPConnection(*server.server_address,timeout=2)
            connection.request(method,path,headers=headers)
            response=connection.getresponse();assert response.status==expected;response.read();connection.close()
        assert calls==[('GET',None)]
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)
