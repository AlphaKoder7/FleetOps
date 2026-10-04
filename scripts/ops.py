"""Guarded Ansible entry point: only recorded FleetOps guest inventory."""

import argparse
import datetime
import json
import ipaddress
import os
from pathlib import Path
import subprocess
import sys

import yaml
import local


def inventory_guard():
    state = local.load()
    inventory = local.ROOT / "ansible/inventories/local/hosts.yml"
    data = yaml.safe_load(inventory.read_text())
    groups = data["all"]["children"]
    hosts = {}
    for group in ("load_balancers", "application_nodes"):
        hosts.update(groups[group]["hosts"])
    if data["all"].get("vars", {}).get("ansible_connection", "ssh") != "ssh":
        raise RuntimeError("Controller/local connection is forbidden")
    if set(hosts) != set(local.NAMES) or set(groups) != {
        "load_balancers",
        "application_nodes",
    }:
        raise RuntimeError(
            "Inventory must contain exactly the recorded FleetOps guests"
        )
    for name, item in hosts.items():
        if item.get("ansible_connection") != "ssh" or item["ansible_host"] != state[
            "domains"
        ][name].get("ip"):
            raise RuntimeError(
                "Inventory address/connection does not match recorded guest"
            )
        address = ipaddress.ip_address(item["ansible_host"])
        if address not in ipaddress.ip_network(state["subnet"]) or address.is_loopback:
            raise RuntimeError("Guest address must be in FleetOps network")
        if not local.assert_owned("domain", name, state["domains"][name]["uuid"]):
            raise RuntimeError("Recorded guest missing")
    return inventory


def ansible(action, extra=()):
    inventory = inventory_guard()
    env = os.environ.copy()
    env["ANSIBLE_HOST_KEY_CHECKING"] = "True"
    env["ANSIBLE_SSH_ARGS"] = (
        f'-F /dev/null -o UserKnownHostsFile={local.RUNTIME / "known_hosts"} -o StrictHostKeyChecking=yes'
    )
    env["ANSIBLE_HOME"] = str(local.RUNTIME / "ansible-home")
    env["ANSIBLE_CONFIG"] = str(local.ROOT / "ansible/ansible.cfg")
    env["ANSIBLE_LOCAL_TEMP"] = str(local.RUNTIME / "ansible-tmp")
    command = (
        [
            str(local.ROOT / ".venv/bin/ansible"),
            "-i",
            str(inventory),
            "all",
            "-m",
            "ansible.builtin.ping",
        ]
        if action == "ping"
        else [
            str(local.ROOT / ".venv/bin/ansible-playbook"),
            "-i",
            str(inventory),
            str(local.ROOT / f"ansible/playbooks/{action}.yml"),
            *extra,
        ]
    )
    if action == "maintain":
        directory = local.RUNTIME / "maintenance"
        directory.mkdir(exist_ok=True)
        for path in directory.glob("fleetops-web-*.json"):
            path.unlink()
    if action == "check":
        directory = local.RUNTIME / "drift"
        directory.mkdir(exist_ok=True)
        for name in local.NAMES:
            (directory / f"{name}.json").unlink(missing_ok=True)
    code = subprocess.run(command, cwd=local.ROOT / "ansible", env=env).returncode
    if action != "check":
        return 0 if code == 0 else 2
    if code:
        return 2
    hosts = [
        json.loads((directory / f"{name}.json").read_text()) for name in local.NAMES
    ]
    report = aggregate_drift(hosts)
    (directory / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    for host in hosts:
        print(f"{host['host']}: {len(host['findings'])} findings")
    return 1 if report["status"] == "drift" else 0


def aggregate_drift(hosts):
    if {item["host"] for item in hosts} != set(local.NAMES) or len(hosts) != 3:
        raise ValueError("Incomplete/duplicate per-host drift reports")
    if any(not isinstance(item["findings"], list) for item in hosts):
        raise ValueError("Invalid findings schema")
    return dict(
        schema_version=1,
        observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        status="drift" if any(item["findings"] for item in hosts) else "clean",
        hosts=hosts,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=[
            "ping",
            "configure",
            "verify",
            "check",
            "repair",
            "maintain",
            "reboot",
            "inject-drift",
            "snapshot",
            "rejoin",
            "snapshot-lb",
            "invalid-candidate",
        ],
    )
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--diff", action="store_true")
    parser.add_argument("--snapshot-label", choices=["before", "after"])
    parser.add_argument("--force-reboot", action="store_true")
    parser.add_argument("--fail-first", action="store_true")
    args = parser.parse_args()
    variables = {}
    if args.snapshot_label:
        variables["snapshot_label"] = args.snapshot_label
    if args.force_reboot:
        variables["maintain_force_reboot"] = True
    if args.fail_first:
        variables["maintain_fail_host"] = "fleetops-web-1"
    extra = (["--check"] if args.check else []) + (["--diff"] if args.diff else [])
    if variables:
        extra.extend(["-e", json.dumps(variables)])
    try:
        return ansible(args.action, extra)
    except (RuntimeError, ValueError, OSError, KeyError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
