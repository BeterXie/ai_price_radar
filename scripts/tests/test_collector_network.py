from scripts import collector_firewall
import json


def test_bridge_rules_only_allow_the_worker_gateway_and_block_metadata(monkeypatch):
    commands=[]
    def read_rules(args,**kwargs):
        commands.append(args)
        if args[0] == 'docker':
            return json.dumps([{'Driver':'bridge','Options':{'com.docker.network.bridge.name':'br-pm-collect'},'IPAM':{'Config':[{'Subnet':'172.30.93.0/24','Gateway':'172.30.93.1'}]}}])
        return ''
    monkeypatch.setattr(collector_firewall.subprocess,'check_output',read_rules)
    programs=[]
    monkeypatch.setattr(collector_firewall.subprocess,'run',lambda args,**kwargs:programs.append(kwargs['input']))
    collector_firewall.main()
    content=programs[0]
    assert '-d 169.254.0.0/16 -j REJECT' in content
    assert '-d 100.64.0.0/10 -j REJECT' in content
    assert '-d 168.63.129.16/32 -j REJECT' in content
    assert '-d 129.146.71.73/32 -j REJECT' in content
    assert '-d 120.26.109.131/32 -j REJECT' in content
    accepts=[line for line in content.splitlines() if 'ACCEPT' in line]
    assert len(accepts)==2 and all('172.30.93.1' in line and '18081' in line for line in accepts)
    assert not any('-F' in command and command[-1] in {'INPUT','FORWARD','DOCKER-USER'} for command in commands)
