"""Root-only guest HAProxy socket operations with bounded health/drain waits."""

import argparse
import csv
from io import StringIO
import json
import socket
import sys
import time

SOCKET = "/run/haproxy/fleetops-admin.sock"
NODES = ("fleetops-web-1", "fleetops-web-2")


def query(command):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(3)
        client.connect(SOCKET)
        client.sendall((command + "\n").encode())
        client.shutdown(socket.SHUT_WR)
        blocks = []
        while chunk := client.recv(65536):
            blocks.append(chunk)
    return b"".join(blocks).decode()


def parse_stats(text):
    reader = csv.DictReader(StringIO(text.lstrip("# ")))
    rows = {
        row["svname"]: row
        for row in reader
        if row["pxname"] == "fleetops_apps" and row["svname"] in NODES
    }
    if set(rows) != set(NODES):
        raise ValueError("Incomplete HAProxy backend statistics")
    return {
        name: {
            "status": row["status"],
            "active": int(row["scur"]),
            "queued": int(row["qcur"]),
        }
        for name, row in rows.items()
    }


def snapshot():
    return parse_stats(query("show stat"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=[
            "snapshot",
            "check-all",
            "disable",
            "enable",
            "wait-drained",
            "wait-up",
        ],
    )
    parser.add_argument("node", nargs="?", choices=NODES)
    parser.add_argument("--timeout", type=float, default=45)
    args = parser.parse_args()
    if args.action not in ("snapshot", "check-all") and not args.node:
        parser.error("A FleetOps backend name is required")
    try:
        if args.action in ("disable", "enable"):
            response = query(
                f'set server fleetops_apps/{args.node} state {"maint" if args.action == "disable" else "ready"}'
            )
            if response.strip():
                raise RuntimeError(response)
        deadline = time.monotonic() + args.timeout
        while True:
            state = snapshot()
            if args.action == "check-all" and any(
                value["status"] != "UP" for value in state.values()
            ):
                raise RuntimeError(
                    "Fleet backend preflight is not healthy: " + json.dumps(state)
                )
            if args.action == "wait-drained":
                ready = (
                    state[args.node]["status"].startswith("MAINT")
                    and state[args.node]["active"] == 0
                    and state[args.node]["queued"] == 0
                )
            elif args.action == "wait-up":
                ready = state[args.node]["status"] == "UP"
            else:
                ready = True
            if ready:
                print(json.dumps(state))
                return 0
            if time.monotonic() >= deadline:
                raise RuntimeError("Backend gate timed out: " + json.dumps(state))
            time.sleep(0.5)
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
