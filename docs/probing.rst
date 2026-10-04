Probe measurement contract
==========================

The host performs sequential HTTP GETs to the private HAProxy address. Defaults: 0.2-second target interval and 2-second per-request timeout. HTTP errors, connection/timeout failures, invalid JSON and invalid node/version schema count as failures. Requests cannot overlap; slow requests reduce sampling frequency. Probes bypass environment proxies to stay on the lab path.

Each raw JSONL observation retains UTC request-start time, HTTP status (null for connection failures), monotonic elapsed latency, returned node/version, success flag and error details where applicable. Summary reports request count, failure count/rate, nearest-rank p95 across all observed requests, successful per-node counts and timing parameters. The observation window is the first through last request-start timestamp, including preflight margin around maintenance. This is an observed lab window, not a zero-downtime guarantee.

Maintenance event timestamps are controller UTC with one-second resolution. Each node's maintenance duration spans started→rejoined; recovery spans recovery-started→direct-ready. Package before/after values are actual dpkg observations. Forced reboot demonstrations also compare actual guest boot IDs. Raw requests and event boundaries remain alongside JSON summaries in evidence. Repeated drills archive previous summaries/raw request files in evidence/history before updating current examples.

Standalone example (substitute the discovered load-balancer address from the ignored inventory):

.. code:: sh

   .venv/bin/python scripts/probe.py http://LOAD_BALANCER_IP:18080/ --seconds 60 --output .runtime/probe.jsonl

The probe exits 1 when any observed request fails; operational errors are not successful observations. No-request summaries fail instead of claiming availability. The host and load-balancer are single points of failure; short GETs do not validate long-lived request drain behavior under load.
