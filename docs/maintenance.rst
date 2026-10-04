Rolling maintenance
===================

``make maintain`` upgrades only ``python3-minimal``, refreshing package metadata separately. Adjust the explicit package set in the playbook and its safety assertion together, review/test, then rerun; no wildcard or whole-OS upgrade is performed. Before/after selected versions are recorded, including unchanged versions when no update exists. Dependencies may be resolved by apt; no OS/package rollback is promised.

``make maintain OPS_ARGS=--force-reboot`` explicitly exercises real guest reboots. The load-balancer and controller are never maintenance targets. A normal run reboots only when ``/var/run/reboot-required`` exists. The reboot module verifies a changed boot ID and reconnects with a timeout.

Before mutation both backends must be healthy; before each drain the alternate node must respond directly. Application play uses sorted order, serial:1 and any_errors_fatal. Selected backend is put in MAINT, active/queued requests must reach zero, then patch/reboot/direct-health/HAProxy-health gates pass before the next node begins. Re-enabling allows HAProxy checks; it does not route requests until the backend is UP.

Failures are explicitly re-raised after excluding the failing backend. The next node does not proceed. Even if a rejoin health gate fails, rescue excludes that backend again. A rescue failure also remains nonzero. Do not treat a rescue execution as success or assume automatic rollback.

Recovery: ``make configure``, then ``.venv/bin/python scripts/ops.py rejoin``, then ``make verify`` and ``make drift-check``. Rejoin first verifies **all** direct application identities/readiness, then enables backends and waits for UP. For a genuinely broken peer, diagnose/repair it before attempting full rejoin.

``make demo DEMO=maintenance`` observes the rolling forced reboot. ``make demo DEMO=abort`` injects a first-node stopped service after reboot, requires nonzero maintenance exit, proves node 2 has no maintenance events and unchanged boot ID, observes failed backend exclusion/healthy peer, then explicitly restores the demo fleet. Production-style ``make maintain`` leaves the failed backend excluded for operator recovery.

Controller event files are in ignored ``.runtime/maintenance``; drill artifacts retain sanitized events and raw probe JSONL. Event timestamps have one-second resolution; probe timestamps/latencies have finer resolution. Serial boundaries prove control-flow order; they do not claim transactional package rollback.

Reproducible actual package upgrade
-----------------------------------

Run ``make demo DEMO=package-upgrade`` on an already configured, healthy FleetOps fleet. The explicit lab profile uses Ubuntu 24.04's ``unzip`` release version ``6.0-28ubuntu4`` and update/security version ``6.0-28ubuntu4.1``. The target is the Ubuntu security fix documented in `USN-7054-1 <https://ubuntu.com/security/notices/USN-7054-1>`__. It uses the existing authenticated Ubuntu repositories; it adds no repository, changes no trust settings, and leaves normal ``make maintain`` selection unchanged. Exact-version installation and the narrowly scoped staging downgrade use supported `Ansible apt parameters <https://docs.ansible.com/projects/ansible/latest/collections/ansible/builtin/apt_module.html>`__.

Continuous HTTP probing starts before maintenance. For each application guest, all existing preflight/alternate-health/drain gates run first. While excluded, the demo refreshes metadata, records ``apt-cache policy unzip`` origins, installs the exact older release version, records ``dpkg-query`` before, upgrades to the exact newer version, and requires both an APT change and the expected ``dpkg-query`` after. It then forces a real guest reboot, verifies direct identity/readiness, rejoins and waits for HAProxy UP before advancing. The load balancer is never patched or rebooted.

This deliberately staged lab upgrade is not evidence of a naturally pending production security update. On repeat runs the demo explicitly downgrades **only unzip** during the drained preparation step, then upgrades it again; this is preparation, not automatic rollback. The older version remains installed only during the exercise. If either pinned version disappears from the authenticated configured repositories, the run fails and excludes the affected node: inspect ``.runtime/maintenance-package-upgrade.log``, review available Ubuntu versions and update both pins/assertions before retrying. Do not bypass package authentication or silently substitute an unchanged version.

Evidence is saved separately in ``evidence/maintenance-package-upgrade.json`` and ``.jsonl``, preserving the previous unchanged-version reboot and abort demonstrations. Repository policy, exact before/after versions, serial/reboot/health boundaries and raw HTTP observations are retained. Portable evidence checks recompute summaries and require peer-only successful serving inside the recorded drain/recovery intervals.

Measured run: UTC 2026-10-04T19:49:12.838291–19:51:28.304125, **678 requests, 0 observed failures, p95 4.74 ms** with 0.2 s interval / 2 s timeout. Node 1 received 352 successful requests and node 2 received 326. Both exact package versions changed and guest boot IDs changed; node 1 rejoined before node 2 started. Evidence tests require successful peer-only observations inside each recorded drain/recovery interval.

+----------------+---------------------------------------+------------------------+
| Guest          | Actual before → after                 | Maintenance / recovery |
+================+=======================================+========================+
| fleetops-web-1 | unzip 6.0-28ubuntu4 → 6.0-28ubuntu4.1 | 58 / 21 seconds        |
+----------------+---------------------------------------+------------------------+
| fleetops-web-2 | unzip 6.0-28ubuntu4 → 6.0-28ubuntu4.1 | 64 / 21 seconds        |
+----------------+---------------------------------------+------------------------+

Both backends ended UP and final fleet verification returned 0. These short sequential GET observations do not establish availability under arbitrary traffic, host failure or long-lived requests. Raw observations and full event/repository records are in the `upgrade summary <../evidence/maintenance-package-upgrade.json>`__ and `request log <../evidence/maintenance-package-upgrade.jsonl>`__.
