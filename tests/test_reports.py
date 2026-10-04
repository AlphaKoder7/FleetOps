from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ops


class DriftReportTests(unittest.TestCase):
    def test_drift_and_clean_are_distinguished(self):
        reports = [dict(host=name, findings=[]) for name in ops.local.NAMES]
        self.assertEqual(ops.aggregate_drift(reports)["status"], "clean")
        reports[1]["findings"].append(dict(kind="service", observed="stopped"))
        self.assertEqual(ops.aggregate_drift(reports)["status"], "drift")

    def test_missing_or_duplicate_host_is_error(self):
        with self.assertRaises(ValueError):
            ops.aggregate_drift([dict(host="fleetops-web-1", findings=[])])
        with self.assertRaises(ValueError):
            ops.aggregate_drift([dict(host="fleetops-web-1", findings=[])] * 3)


class HAProxyParserTests(unittest.TestCase):
    def test_backend_stats_parse_active_and_queued_requests(self):
        import lbctl

        text = "# pxname,svname,scur,qcur,status,\nfleetops_apps,fleetops-web-1,2,1,MAINT,\nfleetops_apps,fleetops-web-2,0,0,UP,\nfleetops_apps,BACKEND,2,1,UP,\n"
        state = lbctl.parse_stats(text)
        self.assertEqual(
            state["fleetops-web-1"], dict(status="MAINT", active=2, queued=1)
        )
        self.assertEqual(state["fleetops-web-2"]["status"], "UP")

    def test_incomplete_backend_stats_are_error(self):
        import lbctl

        with self.assertRaises(ValueError):
            lbctl.parse_stats(
                "# pxname,svname,scur,qcur,status\nfleetops_apps,fleetops-web-1,0,0,UP\n"
            )


class ProbeTests(unittest.TestCase):
    def test_summary_counts_failures_and_nearest_rank_p95(self):
        import probe

        rows = [
            dict(at=str(n), latency_ms=n, success=n != 1, node="fleetops-web-1")
            for n in range(1, 21)
        ]
        report = probe.summarize(rows, interval=0.2, timeout=2)
        self.assertEqual(report["requests"], 20)
        self.assertEqual(report["failures"], 1)
        self.assertEqual(report["failure_rate"], 0.05)
        self.assertEqual(report["p95_latency_ms"], 19)
        self.assertEqual(report["per_node"]["fleetops-web-1"], 19)
        with self.assertRaises(ValueError):
            probe.summarize([], interval=0.2, timeout=2)

    def test_non_200_and_invalid_json_are_failures(self):
        from io import BytesIO
        from unittest.mock import patch
        import probe

        class Response(BytesIO):
            status = 503

        with patch.object(
            probe,
            "urlopen",
            return_value=Response(b'{"node":"fleetops-web-1","version":"1"}'),
        ):
            row = probe.sample("http://unused", 2)
            self.assertEqual(row["status"], 503)
            self.assertFalse(row["success"])
        with patch.object(probe, "urlopen", return_value=Response(b"invalid json")):
            self.assertFalse(probe.sample("http://unused", 2)["success"])


class MaintenanceReportTests(unittest.TestCase):
    def test_event_summary_uses_observed_boundaries_and_actual_versions(self):
        import drills

        events = []
        for stage, timestamp in [
            ("started", "2026-10-04T10:00:00Z"),
            ("patched", "2026-10-04T10:00:02Z"),
            ("recovery-started", "2026-10-04T10:00:03Z"),
            ("ready", "2026-10-04T10:00:10Z"),
            ("rejoined", "2026-10-04T10:00:12Z"),
        ]:
            events.append(
                dict(
                    node="fleetops-web-1",
                    stage=stage,
                    at=timestamp,
                    before=["python3-minimal=1"],
                    after=["python3-minimal=1"],
                )
            )
        report = drills.event_summary(events)["fleetops-web-1"]
        self.assertEqual(report["maintenance_seconds"], 12)
        self.assertEqual(report["recovery_seconds"], 7)
        self.assertEqual(report["package_before"], report["package_after"])


class RecordedEvidenceTests(unittest.TestCase):
    def test_measured_probe_summaries_match_preserved_raw_observations(self):
        import json
        import probe

        root = Path(__file__).resolve().parents[1]
        for label in ["maintenance-reboot", "maintenance-abort"]:
            path = root / f"evidence/{label}.json"
            if not path.exists():
                continue
            report = json.loads(path.read_text())
            rows = [
                json.loads(line)
                for line in (root / f"evidence/{label}.jsonl").read_text().splitlines()
            ]
            measured = probe.summarize(rows, interval=0.2, timeout=2)
            self.assertEqual(measured, report["probe"])
            from datetime import datetime, timedelta

            for node in ["fleetops-web-1", "fleetops-web-2"]:
                stages = {
                    event["stage"]: event
                    for event in report["events"]
                    if event["node"] == node
                }
                if "drained" not in stages:
                    continue
                begin = datetime.fromisoformat(
                    stages["drained"]["at"].replace("Z", "+00:00")
                ) + timedelta(seconds=1)
                terminal = "ready" if "ready" in stages else "failed"
                end = datetime.fromisoformat(
                    stages[terminal]["at"].replace("Z", "+00:00")
                ) - timedelta(seconds=1)
                observations = [
                    row
                    for row in rows
                    if begin <= datetime.fromisoformat(row["at"]) <= end
                ]
                self.assertTrue(observations, "No observations inside drained window")
                self.assertTrue(
                    all(row["success"] and row["node"] != node for row in observations),
                    "Peer must serve during measured drain/recovery interval",
                )


class AcceptanceParserTests(unittest.TestCase):
    def test_idempotency_requires_complete_zero_change_recap(self):
        import integration

        log = "\n".join(
            f"{name} : ok=5 changed=0 unreachable=0 failed=0 skipped=1"
            for name in integration.local.NAMES
        )
        self.assertEqual(len(integration.assert_zero_change(log)), 3)
        for bad in [
            log.replace("changed=0", "changed=1", 1),
            log.splitlines()[0],
            log.replace("failed=0", "failed=1", 1),
        ]:
            with self.assertRaises(ValueError):
                integration.assert_zero_change(bad)

    def test_invalid_candidate_evidence_requires_actual_validator_error(self):
        import drills
        import json

        actual = {
            "msg": "failed to validate",
            "changed": False,
            "exit_status": 1,
            "stderr": "invalid candidate syntax",
        }
        log = "fatal: [fleetops-lb]: FAILED! => " + json.dumps(actual)
        self.assertEqual(drills.invalid_failure(log)["validator_exit_status"], 1)
        actual["msg"] = "cannot connect"
        with self.assertRaises(ValueError):
            drills.invalid_failure(
                "fatal: [fleetops-lb]: FAILED! => " + json.dumps(actual)
            )


class InventoryGuardTests(unittest.TestCase):
    def test_local_connection_and_foreign_guest_address_are_rejected(self):
        from unittest.mock import patch
        import tempfile
        import yaml

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "ansible/inventories/local/hosts.yml"
            path.parent.mkdir(parents=True)
            hosts = {
                name: {
                    "ansible_host": f"192.168.150.{10 + index}",
                    "ansible_connection": "ssh",
                }
                for index, name in enumerate(ops.local.NAMES)
            }
            state = dict(
                subnet="192.168.150.0/24",
                domains={
                    name: {"ip": host["ansible_host"], "uuid": "owned"}
                    for name, host in hosts.items()
                },
            )
            data = {
                "all": {
                    "children": {
                        "load_balancers": {
                            "hosts": {"fleetops-lb": hosts["fleetops-lb"]}
                        },
                        "application_nodes": {
                            "hosts": {name: hosts[name] for name in ops.local.NAMES[1:]}
                        },
                    }
                }
            }
            with patch.object(ops.local, "ROOT", root), patch.object(
                ops.local, "load", return_value=state
            ), patch.object(ops.local, "assert_owned", return_value=True):
                path.write_text(yaml.safe_dump(data))
                self.assertEqual(ops.inventory_guard(), path)
                hosts["fleetops-web-1"]["ansible_connection"] = "local"
                path.write_text(yaml.safe_dump(data))
                with self.assertRaises(RuntimeError):
                    ops.inventory_guard()
                hosts["fleetops-web-1"]["ansible_connection"] = "ssh"
                hosts["fleetops-web-1"]["ansible_host"] = "127.0.0.1"
                path.write_text(yaml.safe_dump(data))
                with self.assertRaises(RuntimeError):
                    ops.inventory_guard()
