"""Generate private Mihomo configuration from an operator-supplied subscription file."""
import argparse
import json
import os
from pathlib import Path
import secrets
import tempfile
import subprocess
from urllib.parse import urlsplit


def configuration(subscription, secret):
    parsed = urlsplit(subscription)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError('Subscription must be an HTTPS URL')
    return {
        'port': 7890, 'allow-lan': False, 'bind-address': '127.0.0.1',
        'authentication': ['collector:' + secret['proxy_password']],
        'external-controller': '127.0.0.1:9090', 'secret': secret['controller_token'],
        'mode': 'rule', 'log-level': 'silent', 'ipv6': False,
        'profile': {'store-selected': True},
        'sniffer': {'enable': True, 'parse-pure-ip': True, 'override-destination': False,
                    'sniff': {'TLS': {'ports': [443], 'override-destination': False}}},
        'proxy-providers': {'subscription': {
            'type': 'http', 'url': subscription, 'path': './providers/subscription.yaml',
            'interval': 86400, 'size-limit': 2 * 1024 * 1024,
            'header': {'User-Agent': ['Clash.Meta']},
            'exclude-filter': '剩余流量|到期时间|重置时间|套餐到期|官网地址',
            'exclude-type': 'hysteria|hysteria2|tuic|wireguard|direct|reject|dns|ssh',
            'override': {'skip-cert-verify': False},
            'health-check': {'enable': False},
        }},
        'proxy-groups': [{'name': '16688-egress', 'type': 'select', 'use': ['subscription']}],
        'rules': [
            'IP-CIDR,0.0.0.0/8,REJECT,no-resolve', 'IP-CIDR,10.0.0.0/8,REJECT,no-resolve',
            'IP-CIDR,100.64.0.0/10,REJECT,no-resolve', 'IP-CIDR,127.0.0.0/8,REJECT,no-resolve',
            'IP-CIDR,169.254.0.0/16,REJECT,no-resolve', 'IP-CIDR,172.16.0.0/12,REJECT,no-resolve',
            'IP-CIDR,192.168.0.0/16,REJECT,no-resolve', 'IP-CIDR,198.18.0.0/15,REJECT,no-resolve',
            'IP-CIDR,224.0.0.0/3,REJECT,no-resolve', 'IP-CIDR6,::/0,REJECT,no-resolve',
            'IP-CIDR,129.146.71.73/32,REJECT,no-resolve', 'IP-CIDR,120.26.109.131/32,REJECT,no-resolve',
            'AND,((DOMAIN,16688.com.cn),(DST-PORT,443)),16688-egress',
            'AND,((DOMAIN,www.16688.com.cn),(DST-PORT,443)),16688-egress',
            'MATCH,REJECT',
        ],
    }


def write_private(path, value):
    descriptor, name = tempfile.mkstemp(dir=path.parent,prefix=path.name+'-',suffix='.tmp')
    temporary=Path(name)
    try:
        with os.fdopen(descriptor,'w') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary.exists():temporary.unlink()


def remove_provider_cache(folder):
    """Never follow a container-created intermediate symlink as root."""
    flags=os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW
    descriptor=os.open(str(folder/'data'),flags)
    try:
        try:providers=os.open('providers',flags,dir_fd=descriptor)
        except FileNotFoundError:return
        try:
            try:os.unlink('subscription.yaml',dir_fd=providers)
            except FileNotFoundError:pass
        finally:os.close(providers)
    finally:os.close(descriptor)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--subscription-file', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=Path('/opt/pricememo-collector'))
    args = parser.parse_args()
    # Bind-mounted single files must be regenerated only while their consumers
    # are stopped, otherwise a live container retains the old inode and secret.
    identities=subprocess.check_output(['docker','ps','-q'],universal_newlines=True).split()
    for identity in identities:
        mounts=json.loads(subprocess.check_output(['docker','inspect','--format','{{json .Mounts}}',identity],universal_newlines=True))
        if any(Path(item['Source'])==args.root/'proxy/config.yaml' for item in mounts):
            raise RuntimeError('Stop the dedicated proxy stack before changing its configuration')
    subscription = args.subscription_file.read_text().strip()
    key = args.root / 'secrets/16688-proxy.key'
    key.parent.mkdir(mode=0o750,parents=True, exist_ok=True)
    folder = args.root / 'proxy'
    folder.mkdir(mode=0o750, exist_ok=True)
    gateway_key=folder/'gateway.key'
    secret = json.loads(gateway_key.read_text()) if gateway_key.exists() else {
        'proxy_password': secrets.token_hex(32), 'controller_token': secrets.token_hex(32)}
    config = configuration(subscription, secret)
    (folder / 'data').mkdir(mode=0o700, exist_ok=True)
    (folder / 'state').mkdir(mode=0o700, exist_ok=True)
    existing=folder/'config.yaml'
    if existing.exists():
        previous=json.loads(existing.read_text())
        if previous.get('proxy-providers',{}).get('subscription',{}).get('url')!=subscription:
            remove_provider_cache(folder)
            quarantine=folder/'state/quarantine.json'
            if quarantine.exists():quarantine.unlink()
    write_private(key, {'proxy_password':secret['proxy_password']})
    write_private(gateway_key,secret)
    write_private(folder / 'config.yaml', config)
    if os.name == 'posix':
        for path in (key, gateway_key, folder, folder / 'config.yaml', folder / 'data', folder/'state'):
            os.chown(str(path), 10001, 10001)
    print(json.dumps({'configured': True, 'subscription_logged': False, 'host_ports_published': False}))


if __name__ == '__main__':
    main()
