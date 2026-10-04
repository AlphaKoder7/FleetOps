import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    "doctor", Path(__file__).resolve().parents[1] / "scripts/doctor.py"
)
doctor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doctor)


class DoctorTests(unittest.TestCase):
    def test_overlapping_route_and_network_are_excluded(self):
        self.assertEqual(
            doctor.candidate_subnet(
                ["default", "192.168.150.0/23"], ["192.168.152.0/24"]
            ),
            "192.168.153.0/24",
        )

    def test_ipv6_does_not_conflict_with_ipv4(self):
        self.assertEqual(doctor.candidate_subnet(["fe80::/64"], []), "192.168.150.0/24")

    def test_exhaustion_fails(self):
        with self.assertRaises(ValueError):
            doctor.candidate_subnet(["192.168.0.0/16"], [])

    def test_memory_parser_uses_available_not_free(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "meminfo"
            path.write_text("MemFree: 1 kB\nMemAvailable: 4096 kB\n")
            self.assertEqual(doctor.memory_available(path), 4194304)
            path.write_text("MemFree: 1 kB\n")
            with self.assertRaises(ValueError):
                doctor.memory_available(path)

    def test_missing_command_is_error(self):
        code, _, error = doctor.command(["/nonexistent/fleetops-command"])
        self.assertEqual(code, 2)
        self.assertTrue(error)
