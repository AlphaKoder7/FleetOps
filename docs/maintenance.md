# Rolling maintenance

`make maintain` upgrades only `python3-minimal`, refreshing package metadata separately. Adjust the explicit package set in the playbook and its safety assertion together, review/test, then rerun; no wildcard or whole-OS upgrade is performed. Before/after selected versions are recorded, including unchanged versions when no update exists. Dependencies may be resolved by apt; no OS/package rollback is promised.

`make maintain OPS_ARGS=--force-reboot` explicitly exercises real guest reboots. The load-balancer and controller are never maintenance targets. A normal run reboots only when `/var/run/reboot-required` exists. The reboot module verifies a changed boot ID and reconnects with a timeout.

Before mutation both backends must be healthy; before each drain the alternate node must respond directly. Application play uses sorted order, serial:1 and any_errors_fatal. Selected backend is put in MAINT, active/queued requests must reach zero, then patch/reboot/direct-health/HAProxy-health gates pass before the next node begins. Re-enabling allows HAProxy checks; it does not route requests until the backend is UP.

Failures are explicitly re-raised after excluding the failing backend. The next node does not proceed. Even if a rejoin health gate fails, rescue excludes that backend again. A rescue failure also remains nonzero. Do not treat a rescue execution as success or assume automatic rollback.

Recovery: `make configure`, then `.venv/bin/python scripts/ops.py rejoin`, then `make verify` and `make drift-check`. Rejoin first verifies **all** direct application identities/readiness, then enables backends and waits for UP. For a genuinely broken peer, diagnose/repair it before attempting full rejoin.

`make demo DEMO=maintenance` observes the rolling forced reboot. `make demo DEMO=abort` injects a first-node stopped service after reboot, requires nonzero maintenance exit, proves node 2 has no maintenance events and unchanged boot ID, observes failed backend exclusion/healthy peer, then explicitly restores the demo fleet. Production-style `make maintain` leaves the failed backend excluded for operator recovery.

Controller event files are in ignored `.runtime/maintenance`; drill artifacts retain sanitized events and raw probe JSONL. Event timestamps have one-second resolution; probe timestamps/latencies have finer resolution. Serial boundaries prove control-flow order; they do not claim transactional package rollback.
