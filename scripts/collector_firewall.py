"""Apply only the dedicated collection bridge's egress and host-access rules."""
import subprocess
import json

BRIDGE = 'br-pm-collect'
# OCI maps the public address outside the host: a public-IP hairpin does not
# traverse INPUT with the Docker bridge as ingress. Block it before that NAT.
HOST_ENDPOINTS = ['129.146.71.73/32', '120.26.109.131/32']
PRIVATE = ['0.0.0.0/8','10.0.0.0/8','100.64.0.0/10','127.0.0.0/8','169.254.0.0/16',
           '172.16.0.0/12','192.168.0.0/16','198.18.0.0/15','224.0.0.0/4','240.0.0.0/4','168.63.129.16/32']


def apply(binary, chains, jumps):
    # iptables-restore commits the complete table transaction at once; old
    # rules remain enforced if validation fails. Never flush shared chains.
    lines=['*filter']
    for name,rules in chains.items():
        lines += [':'+name+' - [0:0]', '-F '+name]
        lines += ['-A '+name+' '+rule for rule in rules]
    for parent,name in jumps:
        # -C errors when the jump target does not yet exist on first install.
        existing = subprocess.check_output([binary,'-w','-S',parent], universal_newlines=True).splitlines()
        rule = parent+' -i '+BRIDGE+' -j '+name
        for existing_rule in existing:
            if existing_rule == '-A '+rule:
                lines.append('-D '+rule)
        lines.append('-I '+parent+' 1 -i '+BRIDGE+' -j '+name)
    lines.append('COMMIT')
    content='\n'.join(lines)+'\n'
    for args in ([binary+'-restore','--noflush','--test'],[binary+'-restore','--noflush','--wait','5']):
        subprocess.run(args,input=content,universal_newlines=True,check=True)


def main():
    network = json.loads(subprocess.check_output(['docker','network','inspect','pricememo_collection'], universal_newlines=True))[0]
    networks = network['IPAM']['Config']
    if network['Driver'] != 'bridge' or network['Options'].get('com.docker.network.bridge.name') != BRIDGE or network.get('EnableIPv6') or len(networks) != 1 or networks[0].get('Subnet') != '172.30.93.0/24' or networks[0].get('Gateway') != '172.30.93.1':
        raise RuntimeError('collector network does not match the isolated bridge policy')
    apply('iptables', {
        'PMCOLLECT_INPUT':['-d 172.30.93.1 -p tcp --dport 18081 -j ACCEPT','-j REJECT'],
        'PMCOLLECT_EGRESS':['-d 172.30.93.1 -p tcp --dport 18081 -j ACCEPT']+['-d '+cidr+' -j REJECT' for cidr in PRIVATE + HOST_ENDPOINTS]+[
            '-p tcp -m multiport --dports 53,80,443 -j RETURN', '-p udp --dport 53 -j RETURN', '-j REJECT'],
    }, [('INPUT','PMCOLLECT_INPUT'),('DOCKER-USER','PMCOLLECT_EGRESS')])
    apply('ip6tables', {'PMCOLLECT6_DENY':['-j REJECT']}, [('INPUT','PMCOLLECT6_DENY'),('FORWARD','PMCOLLECT6_DENY')])
    print('Collection bridge policy applied')


if __name__ == '__main__':
    main()
