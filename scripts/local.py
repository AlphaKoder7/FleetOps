"""FleetOps-only libvirt lifecycle; no sudo, container inspection or cloud credentials."""
import argparse
import fcntl
import grp
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import pwd
import shlex
import subprocess
import sys
import time
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

import doctor

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / '.runtime'
STATE = RUNTIME / 'fleet.json'
NAMES = ('fleetops-lb', 'fleetops-web-1', 'fleetops-web-2')
NETWORK = 'fleetops-net'
IMAGE = 'noble-server-cloudimg-amd64.img'
IMAGE_URL = 'https://cloud-images.ubuntu.com/noble/current/'


def run(args, *, check=True, timeout=120):
    print('+', shlex.join(map(str, args)), flush=True)
    result = subprocess.run(list(map(str, args)), capture_output=True, text=True, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f'Command failed: {args[0]}')
    return result


def virsh(*args, check=True, timeout=120):
    command = ['virsh', '-c', 'qemu:///system', *map(str, args)]
    group = grp.getgrnam('libvirt')
    if group.gr_gid not in os.getgroups() and group.gr_gid != os.getgid():
        if pwd.getpwuid(os.getuid()).pw_name not in group.gr_mem:
            raise RuntimeError('User is not a configured member of libvirt; see README')
        command = ['sg', 'libvirt', '-c', shlex.join(command)]
    return run(command, check=check, timeout=timeout)


def save(state):
    temporary = STATE.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, indent=2) + '\n')
    temporary.chmod(0o600)
    temporary.replace(STATE)


def validate_state(state):
    owner = str(uuid.UUID(state['owner']))
    if state['project'] != str(ROOT) or state['network']['name'] != NETWORK:
        raise RuntimeError('Ownership manifest does not belong to this checkout')
    if tuple(state['domains']) != NAMES:
        raise RuntimeError('Manifest contains unexpected domain names')
    expected_pool = f'fleetops-{owner}'
    if state['pool']['name'] != expected_pool or state['pool']['path'] != f'/var/lib/libvirt/images/{expected_pool}':
        raise RuntimeError('Unexpected storage pool ownership/path')
    uuid.UUID(state['pool']['uuid'])
    uuid.UUID(state['network']['uuid'])
    for name, node in state['domains'].items():
        uuid.UUID(node['uuid'])
        if node['disk'] != name + '.qcow2' or node['seed'] != name + '-seed.img':
            raise RuntimeError('Unexpected volume name')
        if not node['mac'].startswith('52:54:00:'):
            raise RuntimeError('Unexpected MAC address')
    ipaddress.ip_network(state['subnet'])
    return state


def assert_owned(kind, name, expected_uuid):
    result = virsh({'domain': 'domuuid', 'network': 'net-uuid', 'pool': 'pool-uuid'}[kind], name, check=False)
    if result.returncode:
        # A successful name listing distinguishes absence from permission/connection errors.
        listing = virsh({'domain': 'list', 'network': 'net-list', 'pool': 'pool-list'}[kind], '--all', '--name')
        if name not in listing.stdout.splitlines():
            return False
        raise RuntimeError(result.stderr)
    if result.stdout.strip() != expected_uuid:
        raise RuntimeError(f'Refusing to touch unowned {kind}: {name}')
    if kind == 'domain':
        xml = ET.fromstring(virsh('dumpxml', name, '--inactive').stdout)
        if xml.findtext('description') != f'FleetOps {ROOT} owner={load()["owner"]}':
            raise RuntimeError(f'Domain ownership marker mismatch: {name}')
    return True


def load():
    return validate_state(json.loads(STATE.read_text()))


def network_xml(state):
    subnet = ipaddress.ip_network(state['subnet'])
    return f'''<network><name>{NETWORK}</name><uuid>{state['network']['uuid']}</uuid>
<bridge name="fleetops-br0" stp="on" delay="0"/><forward mode="nat"/>
<ip address="{subnet[1]}" prefix="{subnet.prefixlen}"><dhcp><range start="{subnet[10]}" end="{subnet[200]}"/></dhcp></ip></network>'''


def domain_xml(state, name):
    node = state['domains'][name]
    folder = state['pool']['path']
    return f'''<domain type="kvm"><name>{name}</name><uuid>{node['uuid']}</uuid>
<description>{escape(f'FleetOps {ROOT} owner={state["owner"]}')}</description>
<memory unit="MiB">1024</memory><vcpu>1</vcpu><os><type arch="x86_64">hvm</type><boot dev="hd"/></os>
<features><acpi/><apic/></features><cpu mode="host-passthrough"/><clock offset="utc"/>
<on_poweroff>destroy</on_poweroff><on_reboot>restart</on_reboot><on_crash>destroy</on_crash>
<devices><emulator>/usr/bin/qemu-system-x86_64</emulator>
<disk type="file" device="disk"><driver name="qemu" type="qcow2"/><source file="{folder}/{node['disk']}"/><target dev="vda" bus="virtio"/></disk>
<disk type="file" device="cdrom"><driver name="qemu" type="raw"/><source file="{folder}/{node['seed']}"/><target dev="sda" bus="sata"/><readonly/></disk>
<interface type="network"><mac address="{node['mac']}"/><source network="{NETWORK}"/><model type="virtio"/></interface>
<serial type="pty"><target port="0"/></serial><console type="pty"><target type="serial" port="0"/></console>
<channel type="unix"><target type="virtio" name="org.qemu.guest_agent.0"/></channel><rng model="virtio"><backend model="random">/dev/urandom</backend></rng>
</devices></domain>'''


def write_xml(name, xml):
    path = RUNTIME / name
    path.write_text(xml)
    return path


def new_state(extra_subnets):
    report = doctor.inspect()
    # doctor direct virsh may have stale groups; lifecycle explicitly uses sg.
    blockers = [c for c in report['checks'] if c['status'] != 'pass' and c['name'] not in ('libvirt', 'libvirt-networks')]
    if blockers:
        raise RuntimeError('Preflight blocked: ' + ', '.join(c['name'] for c in blockers))
    virsh('uri')
    routes = json.loads(run(['ip', '-j', 'route', 'show', 'table', 'all']).stdout)
    networks = []
    for name in filter(None, virsh('net-list', '--all', '--name').stdout.splitlines()):
        xml = ET.fromstring(virsh('net-dumpxml', name).stdout)
        for element in xml.findall('ip'):
            networks.append(str(ipaddress.ip_network(f"{element.attrib['address']}/{element.get('prefix') or element.get('netmask')}", strict=False)))
        if name == NETWORK or (xml.find('bridge') is not None and xml.find('bridge').get('name') == 'fleetops-br0'):
            raise RuntimeError('fleetops-net/bridge already exists without a manifest; refusing adoption')
    links = json.loads(run(['ip', '-j', 'link']).stdout)
    if any(link['ifname'] == 'fleetops-br0' for link in links):
        raise RuntimeError('Unowned fleetops-br0 exists')
    docker_subnets = []
    for identity in run(['docker', 'network', 'ls', '--format', '{{.ID}}']).stdout.splitlines():
        info = json.loads(run(['docker', 'network', 'inspect', '--format', '{{json .IPAM.Config}}', identity]).stdout)
        docker_subnets.extend(entry['Subnet'] for entry in info or [] if entry.get('Subnet'))
    subnet = doctor.candidate_subnet([r['dst'] for r in routes if 'dst' in r], networks + docker_subnets + extra_subnets)
    owner = str(uuid.uuid4())
    pool = f'fleetops-{owner}'
    state = dict(schema_version=1, project=str(ROOT), owner=owner, subnet=subnet,
                 network=dict(name=NETWORK, uuid=str(uuid.uuid4())),
                 pool=dict(name=pool, uuid=str(uuid.uuid4()), path=f'/var/lib/libvirt/images/{pool}'),
                 domains={name: dict(uuid=str(uuid.uuid4()), mac='52:54:00:' + ':'.join(f'{b:02x}' for b in os.urandom(3)), disk=name+'.qcow2', seed=name+'-seed.img') for name in NAMES})
    for name in NAMES:
        if virsh('dominfo', name, check=False).returncode == 0:
            raise RuntimeError(f'Unowned domain already exists: {name}')
    save(state)
    return state


def download_image():
    checksum_file = RUNTIME / 'SHA256SUMS'
    with urllib.request.urlopen(IMAGE_URL + 'SHA256SUMS', timeout=60) as source:
        checksum_file.write_bytes(source.read())
    wanted = next((line.split()[0] for line in checksum_file.read_text().splitlines() if line.split()[-1].lstrip('*') == IMAGE), None)
    if not wanted:
        raise RuntimeError('Image absent from official checksum manifest')
    image = RUNTIME / IMAGE
    def digest(path):
        h = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024*1024), b''):
                h.update(chunk)
        return h.hexdigest()
    if not image.exists() or digest(image) != wanted:
        temp = image.with_suffix('.part')
        with urllib.request.urlopen(IMAGE_URL + IMAGE, timeout=120) as source, temp.open('wb') as target:
            shutil_copy(source, target)
        if digest(temp) != wanted:
            raise RuntimeError('Ubuntu image checksum mismatch; image not used')
        temp.replace(image)
    print('Verified official Ubuntu image SHA256:', wanted, flush=True)
    return image, wanted


def shutil_copy(source, target):
    while data := source.read(1024*1024):
        target.write(data)


def ensure_key(path):
    if not path.exists():
        run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', 'fleetops-local', '-f', path])
    path.chmod(0o600)
    return path.with_suffix(path.suffix + '.pub').read_text().strip()


def seed(name, node):
    import yaml
    management_pub = ensure_key(RUNTIME / 'fleetops-ssh')
    hostpath = RUNTIME / f'{name}-host-key'
    hostpub = ensure_key(hostpath)
    data = dict(hostname=name, manage_etc_hosts=True, ssh_pwauth=False, disable_root=True,
                users=[dict(name='fleetops', groups=['sudo'], shell='/bin/bash', lock_passwd=True,
                            sudo='ALL=(ALL) NOPASSWD:ALL', ssh_authorized_keys=[management_pub])],
                ssh_keys=dict(ed25519_private=hostpath.read_text(), ed25519_public=hostpub),
                package_update=True, packages=['python3', 'qemu-guest-agent'],
                runcmd=[['systemctl', 'enable', '--now', 'qemu-guest-agent']])
    userdata = RUNTIME / f'{name}-user-data'
    userdata.write_text('#cloud-config\n' + yaml.safe_dump(data))
    userdata.chmod(0o600)
    metadata = RUNTIME / f'{name}-meta-data'
    metadata.write_text(yaml.safe_dump({'instance-id': node['uuid'], 'local-hostname': name}))
    path = RUNTIME / node['seed']
    run(['cloud-localds', path, userdata, metadata])
    path.chmod(0o600)
    return path


def volume(state, name, capacity, fmt, source=None, backing=None):
    pool = state['pool']['name']
    if virsh('vol-info', name, '--pool', pool, check=False).returncode == 0:
        return
    xml = f'<volume><name>{name}</name><capacity unit="bytes">{capacity}</capacity><target><format type="{fmt}"/></target>'
    if backing:
        xml += f'<backingStore><path>{backing}</path><format type="qcow2"/></backingStore>'
    xml += '</volume>'
    virsh('vol-create', pool, write_xml('fleetops-volume.xml', xml))
    if source:
        virsh('vol-upload', '--pool', pool, name, source, timeout=300)


def ssh(name, address, remote, timeout=30):
    return run(['ssh', '-i', RUNTIME/'fleetops-ssh', '-o', 'IdentitiesOnly=yes', '-o', 'StrictHostKeyChecking=yes', '-o', f'UserKnownHostsFile={RUNTIME / "known_hosts"}', '-o', 'ConnectTimeout=5', f'fleetops@{address}', remote], check=False, timeout=timeout)


def readiness(state):
    import yaml
    inventory = {'all': {'children': {'load_balancers': {'hosts': {}}, 'application_nodes': {'hosts': {}}}, 'vars': dict(ansible_user='fleetops', ansible_ssh_private_key_file=str(RUNTIME/'fleetops-ssh'), ansible_ssh_common_args=f'-o IdentitiesOnly=yes -o UserKnownHostsFile={RUNTIME/"known_hosts"} -o StrictHostKeyChecking=yes', fleetops_subnet=state['subnet'])}}
    for name, node in state['domains'].items():
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            output = virsh('domifaddr', name, '--source', 'lease').stdout
            rows = [line.split() for line in output.splitlines() if node['mac'] in line and 'ipv4' in line]
            if rows:
                address = rows[0][-1].split('/')[0]
                if ipaddress.ip_address(address) not in ipaddress.ip_network(state['subnet']):
                    raise RuntimeError('Discovered address outside owned network')
                node['ip'] = address
                # Trust key provisioned by this controller; never TOFU/keyscan.
                entries = []
                for n, record in state['domains'].items():
                    if 'ip' in record:
                        pub = (RUNTIME / f'{n}-host-key.pub').read_text().split()
                        entries.append(f'{record["ip"]} {pub[0]} {pub[1]}')
                (RUNTIME/'known_hosts').write_text('\n'.join(entries)+'\n')
                if ssh(name, address, 'true').returncode == 0:
                    ready = ssh(name, address, 'sudo cloud-init status --wait', timeout=180)
                    if ready.returncode != 0:
                        raise RuntimeError(f'{name}: cloud-init failed: {ready.stdout} {ready.stderr}')
                    break
            time.sleep(3)
        else:
            raise RuntimeError(f'{name}: SSH/DHCP readiness timed out')
        group = 'load_balancers' if name == NAMES[0] else 'application_nodes'
        inventory['all']['children'][group]['hosts'][name] = {'ansible_host': node['ip']}
        save(state)
    path = ROOT/'ansible/inventories/local/hosts.yml'
    path.write_text(yaml.safe_dump(inventory, sort_keys=False))
    print('Fleet ready; generated', path)


def up(extra_subnets, docker_confirmed):
    if not STATE.exists() and not docker_confirmed:
        raise RuntimeError('Confirm absent inactive/custom Docker subnets using --docker-subnets-reviewed, and supply any --exclude-subnet CIDRs. Only Docker network IPAM is inspected.')
    state = load() if STATE.exists() else new_state(extra_subnets)
    pool = state['pool']
    if not assert_owned('pool', pool['name'], pool['uuid']):
        xml = f'<pool type="dir"><name>{pool["name"]}</name><uuid>{pool["uuid"]}</uuid><target><path>{pool["path"]}</path></target></pool>'
        virsh('pool-define', write_xml('fleetops-pool.xml', xml))
        virsh('pool-build', pool['name'])
    if 'running' not in virsh('pool-info', pool['name']).stdout:
        virsh('pool-start', pool['name'])
    if not assert_owned('network', NETWORK, state['network']['uuid']):
        virsh('net-define', write_xml('fleetops-network.xml', network_xml(state)))
    if 'yes' not in next((line for line in virsh('net-info', NETWORK).stdout.splitlines() if line.startswith('Active:')), ''):
        virsh('net-start', NETWORK)
    image, checksum = download_image()
    if state.get('image_sha256') and state['image_sha256'] != checksum:
        raise RuntimeError('Upstream image changed; preserve existing fleet and rebuild explicitly rather than mixing base images')
    state['image_sha256'] = checksum
    save(state)
    volume(state, 'fleetops-base.qcow2', image.stat().st_size, 'qcow2', source=image)
    for name, node in state['domains'].items():
        if not assert_owned('domain', name, node['uuid']):
            volume(state, node['disk'], 8*1024**3, 'qcow2', backing=pool['path']+'/fleetops-base.qcow2')
            source = seed(name, node)
            volume(state, node['seed'], source.stat().st_size, 'raw', source=source)
            virsh('define', write_xml(f'{name}.xml', domain_xml(state, name)))
        if virsh('domstate', name).stdout.strip() != 'running':
            virsh('start', name)
    readiness(state)


def stop(state):
    for name, node in state['domains'].items():
        if assert_owned('domain', name, node['uuid']) and virsh('domstate', name).stdout.strip() != 'shut off':
            virsh('shutdown', name)
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        if all(virsh('domstate', name).stdout.strip() == 'shut off' for name in NAMES):
            return
        time.sleep(2)
    raise RuntimeError('Graceful shutdown timeout; no forced host/guest cleanup performed')


def destroy(state):
    # Validate every resource before any deletion.
    exists = {name: assert_owned('domain', name, node['uuid']) for name, node in state['domains'].items()}
    net_exists = assert_owned('network', NETWORK, state['network']['uuid'])
    pool_exists = assert_owned('pool', state['pool']['name'], state['pool']['uuid'])
    if pool_exists:
        xml = ET.fromstring(virsh('pool-dumpxml', state['pool']['name']).stdout)
        if xml.findtext('target/path') != state['pool']['path']:
            raise RuntimeError('Pool path mismatch; refusing teardown')
        volumes = set(filter(None, virsh('vol-list', state['pool']['name'], '--name').stdout.splitlines()))
        expected = {'fleetops-base.qcow2'} | {n[key] for n in state['domains'].values() for key in ('disk','seed')}
        if volumes - expected:
            raise RuntimeError('Unexpected volumes in owned pool; refusing teardown')
    for name, present in exists.items():
        if present:
            if virsh('domstate', name).stdout.strip() != 'shut off':
                virsh('destroy', name)
            virsh('undefine', name)
    if net_exists:
        if 'yes' in next((line for line in virsh('net-info', NETWORK).stdout.splitlines() if line.startswith('Active:')), ''):
            virsh('net-destroy', NETWORK)
        virsh('net-undefine', NETWORK)
    if pool_exists:
        for name in volumes:
            virsh('vol-delete', name, '--pool', state['pool']['name'])
        virsh('pool-destroy', state['pool']['name'])
        virsh('pool-delete', state['pool']['name'])
        virsh('pool-undefine', state['pool']['name'])
    for kind, name, identity in [('domain', n, r['uuid']) for n,r in state['domains'].items()] + [('network', NETWORK, state['network']['uuid']), ('pool', state['pool']['name'], state['pool']['uuid'])]:
        if assert_owned(kind,name,identity):
            raise RuntimeError('Teardown verification failed')
    STATE.rename(RUNTIME/f'fleet-destroyed-{state["owner"]}.json')
    (ROOT/'ansible/inventories/local/hosts.yml').unlink(missing_ok=True)
    print('Verified exact FleetOps resources absent; cached image/keys retained locally')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['up', 'down', 'destroy'])
    parser.add_argument('--docker-subnets-reviewed', action='store_true')
    parser.add_argument('--exclude-subnet', action='append', default=[])
    args = parser.parse_args()
    RUNTIME.mkdir(mode=0o700, exist_ok=True)
    with (RUNTIME/'lifecycle.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            if args.action == 'up':
                up(args.exclude_subnet, args.docker_subnets_reviewed)
            elif not STATE.exists():
                raise RuntimeError('No recorded fleet; refusing operation')
            elif args.action == 'down':
                stop(load())
            else:
                destroy(load())
        except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
            print(f'ERROR: {exc}', file=sys.stderr)
            return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
