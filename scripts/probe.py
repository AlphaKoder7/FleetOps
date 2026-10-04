"""Continuous measured HTTP observations and summaries, without third-party deps."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import build_opener, ProxyHandler

urlopen = build_opener(ProxyHandler({})).open


def sample(url, timeout):
    began = time.monotonic()
    result = dict(
        at=datetime.now(timezone.utc).isoformat(),
        status=None,
        node=None,
        version=None,
        success=False,
    )
    try:
        try:
            response = urlopen(url, timeout=timeout)
        except HTTPError as exc:
            response = exc
        with response:
            result["status"] = response.status
            payload = json.loads(response.read(65536))
            result["node"] = payload.get("node")
            result["version"] = payload.get("version")
            result["success"] = (
                response.status == 200
                and payload.get("node") in ("fleetops-web-1", "fleetops-web-2")
                and isinstance(payload.get("version"), str)
            )
            if not result["success"]:
                result["error"] = "HTTP/schema health failure"
    except (OSError, ValueError, AttributeError, URLError) as exc:
        result["error"] = str(exc)
    result["latency_ms"] = (time.monotonic() - began) * 1000
    return result


def summarize(observations, *, interval, timeout):
    if not observations:
        raise ValueError("No observations; cannot claim availability")
    latencies = sorted(row["latency_ms"] for row in observations)
    failures = sum(not row["success"] for row in observations)
    return dict(
        schema_version=1,
        window_start=observations[0]["at"],
        window_end=observations[-1]["at"],
        requests=len(observations),
        failures=failures,
        failure_rate=failures / len(observations),
        p95_latency_ms=latencies[max(0, math.ceil(0.95 * len(latencies)) - 1)],
        per_node=dict(Counter(row["node"] for row in observations if row["success"])),
        interval_seconds=interval,
        timeout_seconds=timeout,
        method="Sequential host HTTP GET; nearest-rank p95; failures include HTTP, connection, timeout and invalid identity/schema",
    )


def collect(url, output, stop, interval=0.2, timeout=2.0):
    rows = []
    with Path(output).open("w") as stream:
        while not stop.is_set():
            started = time.monotonic()
            observation = sample(url, timeout)
            rows.append(observation)
            stream.write(json.dumps(observation) + "\n")
            stream.flush()
            stop.wait(max(0, interval - (time.monotonic() - started)))
    return summarize(rows, interval=interval, timeout=timeout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--seconds", type=float, default=60)
    parser.add_argument("--interval", type=float, default=0.2)
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if min(args.seconds, args.interval, args.timeout) <= 0:
        parser.error("Timing values must be positive")
    stop = threading.Event()
    timer = threading.Timer(args.seconds, stop.set)
    timer.start()
    try:
        report = collect(args.url, args.output, stop, args.interval, args.timeout)
    finally:
        timer.cancel()
    args.output.with_suffix(".summary.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps(report, indent=2))
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
