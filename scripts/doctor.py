"""Read-only host preflight. Never inspect credentials or Docker project state."""

import argparse
import ipaddress
import json
import grp
import pwd
import shlex
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
INSTALL = "sudo apt-get install qemu-kvm libvirt-daemon-system libvirt-clients virtinst cloud-image-utils cpu-checker python3-venv"


def command(args):
    try:
        if args[0] == "virsh":
            group = grp.getgrnam("libvirt")
            if (
                group.gr_gid not in os.getgroups()
                and group.gr_gid != os.getgid()
                and pwd.getpwuid(os.getuid()).pw_name in group.gr_mem
            ):
                args = ["sg", "libvirt", "-c", shlex.join(args)]
        result = subprocess.run(args, capture_output=True, text=True, timeout=10)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except (OSError, KeyError, subprocess.TimeoutExpired) as exc:
        return 2, "", str(exc)


def candidate_subnet(routes, networks, candidates=None):
    occupied = [
        ipaddress.ip_network(value, strict=False)
        for value in routes + networks
        if value != "default"
    ]
    for value in candidates or [f"192.168.{n}.0/24" for n in range(150, 200)]:
        subnet = ipaddress.ip_network(value)
        if not any(
            subnet.version == other.version and subnet.overlaps(other)
            for other in occupied
        ):
            return str(subnet)
    raise ValueError("No conflict-free candidate subnet")


def memory_available(path=Path("/proc/meminfo")):
    for line in path.read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) * 1024
    raise ValueError("MemAvailable missing")


def inspect():
    checks = []

    def add(name, ok, detail, action=""):
        checks.append(
            dict(
                name=name,
                status="pass" if ok else "blocked",
                detail=detail,
                action=action if not ok else "",
            )
        )

    add(
        "workspace",
        Path.cwd().resolve() == ROOT,
        "Run from FleetOps repository root",
        f"cd {ROOT}",
    )
    add(
        "os",
        platform.system() == "Linux",
        platform.system(),
        "Use the intended Linux KVM controller",
    )
    add(
        "python",
        sys.version_info >= (3, 12),
        platform.python_version(),
        "Install Python 3.12+ with venv support",
    )
    for executable in [
        "git",
        "make",
        "ssh",
        "ssh-keygen",
        "ip",
        "ss",
        "virsh",
        "qemu-img",
        "virt-install",
        "cloud-localds",
    ]:
        add(
            executable,
            shutil.which(executable) is not None,
            shutil.which(executable) or "not installed",
            (
                INSTALL
                if executable in ["virsh", "qemu-img", "virt-install", "cloud-localds"]
                else f"Install {executable}"
            ),
        )
    free = shutil.disk_usage(ROOT).free
    add(
        "disk",
        free >= 30 * 1024**3,
        f"{free / 1024**3:.1f} GiB free; reserve 30 GiB for three disks and base image",
        "Free disk space without touching unrelated projects",
    )
    try:
        available = memory_available()
        add(
            "ram",
            available >= 4 * 1024**3,
            f"{available / 1024**3:.1f} GiB available; minimum budget 4 GiB",
            "Provide at least 4 GiB available RAM",
        )
    except (OSError, ValueError) as exc:
        add("ram", False, str(exc), "Run on host with /proc access")
    add(
        "kvm",
        os.access("/dev/kvm", os.R_OK | os.W_OK),
        (
            "KVM device accessible"
            if os.access("/dev/kvm", os.R_OK | os.W_OK)
            else "KVM unavailable in this execution context (host may differ)"
        ),
        'Run kvm-ok on host; enable firmware virtualization if needed; sudo usermod -aG kvm "$USER", then log out/in',
    )
    add(
        "venv",
        (ROOT / ".venv/bin/python").exists(),
        "Project-local Python environment",
        "make setup",
    )
    for executable in ["ansible", "ansible-lint"]:
        path = ROOT / ".venv/bin" / executable
        code, output, error = command([str(path), "--version"])
        add(
            executable,
            code == 0,
            output.splitlines()[0] if output else error,
            "make setup",
        )
    code, output, error = command(["ip", "-j", "route", "show", "table", "all"])
    routes = []
    try:
        if code:
            raise ValueError(error)
        routes = [item["dst"] for item in json.loads(output) if "dst" in item]
        add("routes", True, f"{len(routes)} visible routes inspected")
    except (ValueError, KeyError) as exc:
        add(
            "routes",
            False,
            f"Inspection unavailable: {exc}",
            "Run make doctor outside the restricted sandbox",
        )
    code, output, error = command(["ss", "-H", "-ltn"])
    port_ok = code == 0 and not error
    add(
        "ports",
        port_ok,
        "TCP listener inspection available" if port_ok else error,
        "Run make doctor on host",
    )
    if port_ok:
        conflicts = [
            line
            for line in output.splitlines()
            if any(line.split()[3].endswith(f":{port}") for port in (18080, 18081))
        ]
        add(
            "port-conflicts",
            not conflicts,
            (
                "No host listener on 18080/18081"
                if not conflicts
                else "\n".join(conflicts)
            ),
            "Investigate listener; do not stop unrelated services",
        )
    if shutil.which("docker"):
        docker_ok = True
        code, output, error = command(
            [
                "docker",
                "--host",
                "unix:///var/run/docker.sock",
                "network",
                "ls",
                "--format",
                "{{.ID}}",
            ]
        )
        docker_ok = code == 0
        subnets = []
        if docker_ok:
            for identity in filter(None, output.splitlines()):
                code, config, error = command(
                    [
                        "docker",
                        "--host",
                        "unix:///var/run/docker.sock",
                        "network",
                        "inspect",
                        "--format",
                        "{{json .IPAM.Config}}",
                        identity,
                    ]
                )
                try:
                    if code:
                        raise ValueError(error)
                    subnets.extend(
                        entry["Subnet"]
                        for entry in json.loads(config) or []
                        if entry.get("Subnet")
                    )
                except (ValueError, KeyError):
                    docker_ok = False
        add(
            "docker-ipam",
            docker_ok,
            (
                f"{len(subnets)} Docker subnet ranges inspected read-only"
                if docker_ok
                else error or "IPAM inspection failed"
            ),
            "Provide local Docker socket access; no container inspection is needed",
        )
    else:
        subnets = []
    networks = []
    code, output, error = command(["virsh", "-c", "qemu:///system", "uri"])
    add(
        "libvirt",
        code == 0 and output == "qemu:///system",
        output or error,
        'Install libvirt packages; sudo usermod -aG libvirt,kvm "$USER"; log out/in; verify virsh -c qemu:///system uri',
    )
    network_ok = code == 0
    if network_ok:
        code, output, error = command(
            ["virsh", "-c", "qemu:///system", "net-list", "--all", "--name"]
        )
        network_ok = code == 0
        for name in filter(None, output.splitlines()) if code == 0 else []:
            code, xml, error = command(
                ["virsh", "-c", "qemu:///system", "net-dumpxml", name]
            )
            if code:
                network_ok = False
                break
            try:
                for element in ET.fromstring(xml).findall("ip"):
                    networks.append(
                        str(
                            ipaddress.ip_network(
                                f"{element.attrib['address']}/{element.get('prefix') or element.get('netmask')}",
                                strict=False,
                            )
                        )
                    )
            except (ET.ParseError, ValueError, KeyError):
                network_ok = False
        add(
            "libvirt-networks",
            network_ok,
            (
                f"{len(networks)} subnets inspected"
                if network_ok
                else error or "Cannot parse network XML"
            ),
            "Resolve read-only libvirt network inspection",
        )
    if network_ok and any(
        item["name"] == "routes" and item["status"] == "pass" for item in checks
    ):
        try:
            add(
                "subnet-candidate",
                True,
                candidate_subnet(routes, networks + subnets)
                + " (provisional; recheck before creation)",
            )
        except ValueError as exc:
            add("subnet-candidate", False, str(exc), "Supply a conflict-free subnet")
    return dict(
        schema_version=1,
        status="blocked" if any(c["status"] == "blocked" for c in checks) else "ready",
        checks=checks,
        limitations=[
            "Only local Docker network IPAM is inspected, as authorized; no container or credential data is requested.",
            "No guests, networks, keys or cloud resources are created by doctor.",
        ],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = inspect()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for check in report["checks"]:
            print(f"{check['status'].upper():7} {check['name']}: {check['detail']}")
            if check["action"]:
                print(f"        Action: {check['action']}")
        for note in report["limitations"]:
            print(f"NOTE    {note}")
    return 0 if report["status"] == "ready" else 2


if __name__ == "__main__":
    sys.exit(main())
