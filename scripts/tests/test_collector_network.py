from scripts import collector_firewall
import json
import pytest


@pytest.mark.parametrize('proxy_enabled', [False, True])
def test_bridge_rules_only_allow_the_worker_gateway_and_block_metadata(monkeypatch, proxy_enabled):
    commands=[]
    def read_rules(args,**kwargs):
        commands.append(args)
        if args[0] == 'docker':
            return json.dumps([{'Driver':'bridge','Options':{'com.docker.network.bridge.name':'br-pm-collect'},'IPAM':{'Config':[{'Subnet':'172.30.93.0/24','Gateway':'172.30.93.1'}]}}])
        return ''
    monkeypatch.setattr(collector_firewall.subprocess,'check_output',read_rules)
    programs=[]
    monkeypatch.setattr(collector_firewall.subprocess,'run',lambda args,**kwargs:programs.append(kwargs['input']))
    collector_firewall.main(['--enable-16688-proxy'] if proxy_enabled else [])
    content=programs[0]
    assert '-d 169.254.0.0/16 -j REJECT' in content
    assert '-d 100.64.0.0/10 -j REJECT' in content
    assert '-d 168.63.129.16/32 -j REJECT' in content
    assert '-d 129.146.71.73/32 -j REJECT' in content
    assert '-d 120.26.109.131/32 -j REJECT' in content
    accepts=[line for line in content.splitlines() if 'ACCEPT' in line]
    gateway=[line for line in accepts if '172.30.93.1 ' in line]
    assert len(gateway)==2 and all('18081' in line for line in gateway)
    if proxy_enabled:
        assert len(accepts)==4
        assert '-d 172.30.93.10 -p tcp --dport 7891 -j ACCEPT' in content
        assert '--sport 7891 -m conntrack --ctstate ESTABLISHED -j ACCEPT' in content
        assert '! -s 172.30.93.10' in gateway[0]
        assert content.index('-d 169.254.0.0/16 -j REJECT') < content.index('-s 172.30.93.10 -p tcp -j RETURN')
        assert content.index('-d 120.26.109.131/32 -j REJECT') < content.index('-s 172.30.93.10 -p tcp -j RETURN')
    else:
        assert len(accepts)==2 and '172.30.93.10' not in content
    assert not any('-F' in command and command[-1] in {'INPUT','FORWARD','DOCKER-USER'} for command in commands)
