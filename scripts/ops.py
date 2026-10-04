"""Guarded Ansible entry point: only recorded FleetOps guest inventory."""
import argparse
import ipaddress
import os
from pathlib import Path
import subprocess
import sys

import yaml
import local


def inventory_guard():
    state = local.load()
    inventory = local.ROOT / 'ansible/inventories/local/hosts.yml'
    data = yaml.safe_load(inventory.read_text())
    groups = data['all']['children']
    hosts = {}
    for group in ('load_balancers', 'application_nodes'):
        hosts.update(groups[group]['hosts'])
    if set(hosts) != set(local.NAMES) or set(groups) != {'load_balancers', 'application_nodes'}:
        raise RuntimeError('Inventory must contain exactly the recorded FleetOps guests')
    for name, item in hosts.items():
        if item.get('ansible_connection', 'ssh') != 'ssh' or item['ansible_host'] != state['domains'][name].get('ip'):
            raise RuntimeError('Inventory address/connection does not match recorded guest')
        address = ipaddress.ip_address(item['ansible_host'])
        if address not in ipaddress.ip_network(state['subnet']) or address.is_loopback:
            raise RuntimeError('Guest address must be in FleetOps network')
        if not local.assert_owned('domain', name, state['domains'][name]['uuid']):
            raise RuntimeError('Recorded guest missing')
    return inventory


def ansible(action, extra=()):
    inventory = inventory_guard()
    env = os.environ.copy()
    env['ANSIBLE_HOME'] = str(local.RUNTIME/'ansible-home')
    env['ANSIBLE_CONFIG'] = str(local.ROOT/'ansible/ansible.cfg')
    env['ANSIBLE_LOCAL_TEMP'] = str(local.RUNTIME/'ansible-tmp')
    command = [str(local.ROOT/'.venv/bin/ansible'), '-i', str(inventory), 'all', '-m', 'ansible.builtin.ping'] if action == 'ping' else [str(local.ROOT/'.venv/bin/ansible-playbook'), '-i', str(inventory), str(local.ROOT/f'ansible/playbooks/{action}.yml'), *extra]
    return subprocess.run(command, cwd=local.ROOT/'ansible', env=env).returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['ping', 'configure', 'verify', 'check', 'repair', 'maintain', 'reboot'])
    args, extra = parser.parse_known_args()
    try:
        return ansible(args.action, extra)
    except (RuntimeError, ValueError, OSError, KeyError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
