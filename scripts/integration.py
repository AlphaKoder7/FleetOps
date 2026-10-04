"""Real local VM smoke/idempotency checks; full destructive drills are make demo."""

import json
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess
import sys

import local


def assert_zero_change(log):
    rows = re.findall(
        r"^(fleetops-(?:lb|web-[12]))\s+:\s+ok=\d+\s+changed=(\d+)\s+unreachable=(\d+)\s+failed=(\d+)",
        log,
        re.MULTILINE,
    )
    if (
        len(rows) != 3
        or {row[0] for row in rows} != set(local.NAMES)
        or any(any(int(value) for value in row[1:]) for row in rows)
    ):
        raise ValueError("Incomplete/non-idempotent configuration recap")
    return {
        row[0]: dict(changed=int(row[1]), unreachable=int(row[2]), failed=int(row[3]))
        for row in rows
    }


def main():
    report = {
        "kind": "real-local-vm-integration",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "checks": [],
    }
    for action in ["ping", "verify", "check", "configure", "verify", "check"]:
        path = local.RUNTIME / f"integration-{action}.log"
        with path.open("w") as stream:
            code = subprocess.run(
                [sys.executable, str(local.ROOT / "scripts/ops.py"), action],
                stdout=stream,
                stderr=subprocess.STDOUT,
            ).returncode
        if code:
            print(f"Integration {action} failed with {code}: {path}", file=sys.stderr)
            return 2
        report["checks"].append(dict(action=action, exit_status=code))
        if action == "configure":
            try:
                report["idempotency"] = assert_zero_change(path.read_text())
            except ValueError as exc:
                print(str(exc), file=sys.stderr)
                return 2
    report["verified_at"] = datetime.now(timezone.utc).isoformat()
    (local.ROOT / "evidence/local-integration.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(
        "Real VM reachability, health, clean drift and zero-change configure verified"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
