from scripts.configure_collector_proxy import configuration


def test_subscription_cannot_replace_local_rules_ports_or_tls_policy():
    result=configuration('https://subscription.example/private-token',{'proxy_password':'p'*40,'controller_token':'t'*40})
    assert result['port']==7890 and result['external-controller']=='127.0.0.1:9090'
    assert result['bind-address']=='127.0.0.1' and result['allow-lan'] is False
    assert result['log-level']=='silent'
    assert result['sniffer']['override-destination'] is False
    assert result['proxy-providers']['subscription']['override']['skip-cert-verify'] is False
    assert result['proxy-providers']['subscription']['health-check']['enable'] is False
    assert result['rules'][-1]=='MATCH,REJECT'
    assert 'IP-CIDR,169.254.0.0/16,REJECT,no-resolve' in result['rules']
    assert all('16688-egress' not in rule or 'DST-PORT,443' in rule for rule in result['rules'])
