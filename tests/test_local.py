import copy
import importlib.util
import ipaddress
from pathlib import Path
import sys
import unittest
import uuid
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import local


def manifest():
    owner = str(uuid.uuid4())
    pool = 'fleetops-' + owner
    return dict(owner=owner, project=str(local.ROOT), subnet='192.168.150.0/24',
                network=dict(name='fleetops-net', uuid=str(uuid.uuid4())),
                pool=dict(name=pool, uuid=str(uuid.uuid4()), path='/var/lib/libvirt/images/'+pool),
                domains={name: dict(uuid=str(uuid.uuid4()), mac='52:54:00:01:02:03', disk=name+'.qcow2', seed=name+'-seed.img') for name in local.NAMES})


class OwnershipTests(unittest.TestCase):
    def test_manifest_rejects_foreign_checkout_and_volumes(self):
        state = manifest()
        self.assertEqual(local.validate_state(state), state)
        for path, value in [('project', '/tmp/other'), ('pool', dict(name='default', path='/var/lib/libvirt/images', uuid=str(uuid.uuid4())))]:
            invalid = copy.deepcopy(state)
            invalid[path] = value
            with self.assertRaises(RuntimeError):
                local.validate_state(invalid)
        state['domains']['fleetops-web-1']['disk'] = '../other.qcow2'
        with self.assertRaises(RuntimeError):
            local.validate_state(state)

    def test_domain_network_and_storage_are_project_scoped(self):
        state = manifest()
        xml = ET.fromstring(local.domain_xml(state, 'fleetops-web-1'))
        self.assertEqual(xml.findtext('name'), 'fleetops-web-1')
        self.assertEqual(xml.find('devices/interface/source').get('network'), 'fleetops-net')
        self.assertEqual(xml.find('memory').text, '1024')
        self.assertEqual(xml.find('vcpu').text, '1')
        self.assertIsNone(xml.find('devices/hostdev'))
        for source in xml.findall('devices/disk/source'):
            self.assertTrue(source.get('file').startswith(state['pool']['path'] + '/fleetops-'))

    def test_network_dhcp_range_is_inside_selected_subnet(self):
        state = manifest()
        xml = ET.fromstring(local.network_xml(state))
        subnet = ipaddress.ip_network(state['subnet'])
        self.assertEqual(xml.find('forward').get('mode'), 'nat')
        self.assertEqual(xml.find('bridge').get('name'), 'fleetops-br0')
        for address in xml.find('ip/dhcp/range').attrib.values():
            self.assertIn(ipaddress.ip_address(address), subnet)
