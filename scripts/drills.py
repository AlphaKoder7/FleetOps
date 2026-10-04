"""Real guest drills: assertions, raw logs, and mandatory health restoration."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
import shlex
import shutil
import re
import probe
import ops

import local


def call(action, extras=(), expected=0, label=None):
    log = local.RUNTIME / f"{label or action}.log"
    with log.open("w") as stream:
        result = subprocess.run(
            [sys.executable, str(local.ROOT / "scripts/ops.py"), action, *extras],
            stdout=stream,
            stderr=subprocess.STDOUT,
        )
    print(f"{action}: exit {result.returncode}; log {log}", flush=True)
    if result.returncode != expected:
        raise RuntimeError(
            f"{action}: expected {expected}, got {result.returncode}; inspect {log}"
        )
    return result.returncode


def archive_previous(label):
    summary = local.ROOT / f"evidence/{label}.json"
    raw = local.ROOT / f"evidence/{label}.jsonl"
    if summary.exists() or raw.exists():
        directory = (
            local.ROOT
            / "evidence/history"
            / f'{label}-{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")}'
        )
        directory.mkdir(parents=True)
        for path in (summary, raw):
            if path.exists():
                shutil.copy2(path, directory / path.name)


def drift_drill():
    archive_previous("drift-drill")
    (local.RUNTIME / "snapshots").mkdir(exist_ok=True)
    report = dict(
        kind="simulated-drift-incident",
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    try:
        call("verify")
        call("inject-drift")
        call("snapshot", ["--snapshot-label", "before"], label="snapshot-before")
        call("check", expected=1, label="drift-detected")
        observed = json.loads((local.RUNTIME / "drift/summary.json").read_text())
        host_findings = {item["host"]: item["findings"] for item in observed["hosts"]}
        if not any(
            item["kind"] == "file" and item["path"] == "/etc/fleetops/application.json"
            for item in host_findings["fleetops-web-1"]
        ):
            raise RuntimeError("Setting drift not identified")
        if not any(
            item["kind"] == "service" for item in host_findings["fleetops-web-2"]
        ):
            raise RuntimeError("Stopped service not identified")
        call("snapshot", ["--snapshot-label", "after"], label="snapshot-after")
        snapshots = {}
        for name in local.NAMES[1:]:
            before = json.loads(
                (local.RUNTIME / f"snapshots/before-{name}.json").read_text()
            )
            after = json.loads(
                (local.RUNTIME / f"snapshots/after-{name}.json").read_text()
            )
            snapshots[name] = {"before": before, "after": after}
            if before != after:
                raise RuntimeError(
                    f"Detection altered guest file/service state on {name}"
                )
        report.update(detection=observed, snapshots=snapshots, detection_read_only=True)
    finally:
        call("repair", label="drift-repair")
    call("check", label="drift-clean")
    report.update(
        repaired_at=datetime.now(timezone.utc).isoformat(), final_status="healthy-clean"
    )
    path = local.ROOT / "evidence/drift-drill.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Verified drift detection/repair: {path}")


def boot_id(name):
    state = local.load()
    result = local.ssh(
        name, state["domains"][name]["ip"], "cat /proc/sys/kernel/random/boot_id"
    )
    if result.returncode:
        raise RuntimeError("Cannot observe guest boot ID")
    return result.stdout.strip()


def guest_fingerprint(name):
    state = local.load()
    program = """import hashlib,json,subprocess
from pathlib import Path
print(json.dumps({'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
 'config_sha256':hashlib.sha256(Path('/etc/fleetops/application.json').read_bytes()).hexdigest(),
 'package':subprocess.check_output(['dpkg-query','-W','-f=${Version}','python3-minimal'],text=True),
 'service':subprocess.check_output(['systemctl','show','fleetops-app','-p','ActiveState','-p','NRestarts'],text=True),
 'apt_metadata':{p.name:p.stat().st_mtime_ns for p in Path('/var/lib/apt/lists').iterdir() if p.is_file()}}))"""
    result = local.ssh(
        name, state["domains"][name]["ip"], "python3 -c " + shlex.quote(program)
    )
    if result.returncode:
        raise RuntimeError("Cannot observe node fingerprint")
    return json.loads(result.stdout)


def backend_state():
    state = local.load()
    result = local.ssh(
        "fleetops-lb",
        state["domains"]["fleetops-lb"]["ip"],
        "sudo python3 /opt/fleetops/lbctl.py snapshot",
    )
    if result.returncode:
        raise RuntimeError(result.stderr)
    return json.loads(result.stdout)


def event_summary(events):
    result = {}
    for name in local.NAMES[1:]:
        by_stage = {event["stage"]: event for event in events if event["node"] == name}
        if not by_stage:
            continue

        def seconds(start, end):
            return (
                datetime.fromisoformat(by_stage[end]["at"].replace("Z", "+00:00"))
                - datetime.fromisoformat(by_stage[start]["at"].replace("Z", "+00:00"))
            ).total_seconds()

        result[name] = {
            "stages": sorted(by_stage),
            "package_before": by_stage.get("patched", {}).get("before"),
            "package_after": by_stage.get("patched", {}).get("after"),
        }
        if "rejoined" in by_stage:
            result[name]["maintenance_seconds"] = seconds("started", "rejoined")
            result[name]["recovery_seconds"] = seconds("recovery-started", "ready")
    return result


def maintenance_drill(fail=False, package_upgrade=False):
    ops.inventory_guard()
    label = (
        "maintenance-package-upgrade"
        if package_upgrade
        else "maintenance-abort" if fail else "maintenance-reboot"
    )
    archive_previous(label)
    report = {"kind": label, "started_at": datetime.now(timezone.utc).isoformat()}
    call("verify", label=label + "-preflight")
    untouched_before = guest_fingerprint("fleetops-web-2") if fail else None
    before = {name: boot_id(name) for name in local.NAMES[1:]}
    state = local.load()
    stop = threading.Event()
    results = {}
    raw = local.ROOT / f"evidence/{label}.jsonl"

    def observe():
        try:
            results["probe"] = probe.collect(
                f"http://{state['domains']['fleetops-lb']['ip']}:18080/", raw, stop
            )
        except Exception as exc:
            results["error"] = str(exc)

    thread = threading.Thread(target=observe)
    thread.start()
    exercise_failed = False
    try:
        time.sleep(2)
        call(
            "maintain",
            ["--force-reboot"]
            + (["--fail-first"] if fail else [])
            + (["--package-upgrade-demo"] if package_upgrade else []),
            expected=2 if fail else 0,
            label=label,
        )
        events = [
            json.loads(path.read_text())
            for path in sorted(
                (local.RUNTIME / "maintenance").glob("fleetops-web-*.json")
            )
        ]
        after = {name: boot_id(name) for name in local.NAMES[1:]}
        backend = backend_state()
        if fail:
            untouched_after = guest_fingerprint("fleetops-web-2")
            if untouched_before != untouched_after:
                raise RuntimeError(
                    "Failure altered node 2 managed state/package metadata"
                )
            report["untouched_peer"] = {
                "before": untouched_before,
                "after": untouched_after,
            }
            if (
                any(event["node"] == "fleetops-web-2" for event in events)
                or before["fleetops-web-2"] != after["fleetops-web-2"]
            ):
                raise RuntimeError("Failure allowed maintenance on node 2")
            if (
                not backend["fleetops-web-1"]["status"].startswith("MAINT")
                or backend["fleetops-web-2"]["status"] != "UP"
            ):
                raise RuntimeError(
                    "Failed backend not excluded or healthy peer unavailable"
                )
        else:
            by_node = {
                name: {
                    event["stage"]: event for event in events if event["node"] == name
                }
                for name in local.NAMES[1:]
            }
            if (
                by_node["fleetops-web-1"]["rejoined"]["at"]
                > by_node["fleetops-web-2"]["started"]["at"]
            ):
                raise RuntimeError("Serial maintenance boundaries overlap")
            if any(before[name] == after[name] for name in local.NAMES[1:]):
                raise RuntimeError("Forced reboot did not change each guest boot ID")
        if package_upgrade:
            for node, measured in event_summary(events).items():
                if measured["package_before"] != ["unzip=6.0-28ubuntu4"] or measured[
                    "package_after"
                ] != ["unzip=6.0-28ubuntu4.1"]:
                    raise RuntimeError(
                        f"Actual package upgrade not demonstrated on {node}"
                    )
            report["setup"] = {
                "package": "unzip",
                "staged_version": "6.0-28ubuntu4",
                "target_version": "6.0-28ubuntu4.1",
                "method": "Authenticated Ubuntu APT; stage release version while drained, then upgrade exact version",
                "repeat_run": "Explicit demo permits downgrading only unzip during staging",
            }
        report.update(
            events=events,
            per_node=event_summary(events),
            boot_before=before,
            boot_after=after,
            backend_after=backend,
            exit_status=2 if fail else 0,
        )
    except Exception:
        exercise_failed = True
        raise
    finally:
        if fail or exercise_failed:
            call("configure", label=label + "-restore-config")
            call("rejoin", label=label + "-restore-backends")
        time.sleep(2)
        stop.set()
        thread.join(timeout=5)
        if thread.is_alive() or "error" in results:
            raise RuntimeError(
                "Probe failed: " + results.get("error", "thread did not stop")
            )
    call("verify", label=label + "-final-verify")
    report.update(
        probe=results["probe"],
        restored_at=datetime.now(timezone.utc).isoformat(),
        final_status="healthy",
    )
    path = local.ROOT / f"evidence/{label}.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(results["probe"], indent=2), flush=True)
    print(f"Verified maintenance drill: {path}")


def invalid_failure(log):
    failed = next(
        (
            line
            for line in log.splitlines()
            if line.startswith("fatal: [fleetops-lb]: FAILED! => ")
        ),
        None,
    )
    if not failed:
        raise ValueError("Missing explicit validator failure result")
    result = json.loads(failed.split("=>", 1)[1])
    if (
        result.get("msg") != "failed to validate"
        or result.get("exit_status") != 1
        or result.get("changed") is not False
    ):
        raise ValueError("Failure was not a no-change candidate validation rejection")
    return {
        "validator_exit_status": result["exit_status"],
        "message": result["msg"],
        "stderr": re.sub(
            r"/home/fleetops/\.ansible/tmp/[^\s\]:]+", "<candidate>", result["stderr"]
        ),
    }


def invalid_drill():
    archive_previous("invalid-candidate")
    (local.RUNTIME / "snapshots").mkdir(exist_ok=True)
    report = {
        "kind": "invalid-candidate",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        call("snapshot-lb", ["--snapshot-label", "before"], label="invalid-before")
        call("invalid-candidate", expected=2)
        report["validation"] = invalid_failure(
            (local.RUNTIME / "invalid-candidate.log").read_text()
        )
        call("snapshot-lb", ["--snapshot-label", "after"], label="invalid-after")
        before = json.loads(
            (local.RUNTIME / "snapshots/before-fleetops-lb.json").read_text()
        )
        after = json.loads(
            (local.RUNTIME / "snapshots/after-fleetops-lb.json").read_text()
        )
        if before != after:
            raise RuntimeError("Invalid candidate altered active configuration/service")
        report.update(
            exit_status=2,
            before=before,
            after=after,
            rejection_preserved_active_state=True,
        )
    except Exception:
        call("configure", label="invalid-recover")
        raise
    finally:
        call("verify", label="invalid-final-verify")
    call("check", label="invalid-final-clean")
    report.update(
        verified_at=datetime.now(timezone.utc).isoformat(), final_status="healthy-clean"
    )
    (local.ROOT / "evidence/invalid-candidate.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print("Verified invalid candidate rejection and final healthy/clean state")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=["drift", "maintenance", "package-upgrade", "abort", "invalid", "all"],
    )
    args = parser.parse_args()
    try:
        if args.action == "all":
            drift_drill()
            maintenance_drill()
            maintenance_drill(fail=True)
            invalid_drill()
        elif args.action == "package-upgrade":
            maintenance_drill(package_upgrade=True)
        elif args.action == "invalid":
            invalid_drill()
        elif args.action == "drift":
            drift_drill()
        else:
            maintenance_drill(fail=args.action == "abort")
    except (RuntimeError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
