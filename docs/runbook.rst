FleetOps runbook
================

All commands run from this checkout and target recorded FleetOps guests. Keep .runtime/fleet.json and private management keys; never fall back to localhost, adopt another network/pool, or run broad cleanup. AWS provisioning remains disabled.

Unreachable guest
-----------------

1. Run ``make doctor`` in a host terminal. Sandbox-hidden devices/routes/sockets are inspection errors, not proof of absent prerequisites.
2. Run ``make up``; it checks exact UUIDs, starts stopped guests and rediscovers DHCP addresses. Preserve the manifest on failure.
3. Inspect only the exact guest with ``sg libvirt -c 'virsh -c qemu:///system domstate fleetops-web-1'`` (substitute another recorded exact name). Use its serial console if boot diagnostics are needed; leave unrelated guests/services alone.
4. Use the generated inventory's management identity/address and .runtime/known_hosts. Do not disable host-key checking to “fix” a mismatch. The host keys were provisioned from project-owned cloud-init seeds: diagnose lost/changed ownership or rebuild with verified teardown.
5. Cloud-init failures and readiness timeouts are errors; check that guest's cloud-init/journald logs through pinned SSH once reachable. Never collect passwords.

Bad configuration or stopped workload
-------------------------------------

``make drift-check`` identifies the defined managed files/permissions, packages and enabled/running service state. It does not repair them. Read ``.runtime/drift/summary.json``. Direct checker exit 1 means drift; 2 means incomplete/operational failure. Candidate application JSON and HAProxy configuration must validate before activation. Do not bypass validation or overwrite the active file with an untested candidate.

Run ``make repair``, then ``make drift-check`` and ``make verify``. Inspect guest-only ``sudo journalctl -u fleetops-app`` or ``sudo journalctl -u haproxy`` through the pinned management key if recovery fails. Non-root workload settings/code are root-owned; journal logs explain service crashes.

.. _drained-backend--failed-maintenance:

Drained backend / failed maintenance
------------------------------------

A maintenance error returns nonzero and intentionally leaves the failing backend excluded; the load-balancer and host are never reboot targets. Read ``.runtime/maintenance/fleetops-web-1-failed.json`` and the command log. Diagnose the direct endpoint and selected package before/after versions. Do not continue node 2 or treat rescue as success.

1. Restore known-good configuration/service with ``make configure``. This does not roll back packages or OS state.
2. ``.venv/bin/python scripts/ops.py rejoin`` verifies direct readiness/identity for both application nodes, enables backends via the root-only socket, and waits for HAProxy UP. It fails before rejoin when direct health is bad.
3. ``make verify`` and ``make drift-check`` must pass before another maintenance run.

``make repair`` includes distribution verification, so it can return nonzero while an intentionally drained backend remains excluded. Use the explicit configure→rejoin→verify sequence above. For a package/OS regression that roles cannot fix, inspect actual versions and plan manual recovery or a scoped lab rebuild; no automatic downgrade guarantee exists.

Start, stop and rebuild
-----------------------

``make down`` gracefully stops only the recorded domains; ``make up`` starts them and preserves disks. Stop timeouts do not force broad cleanup. ``make destroy`` verifies every resource UUID, storage path and allowed volume set before deleting. It also verifies recorded resource absence, retaining local downloads/SSH material. Destroy failures leave the manifest for diagnosis/retry.

For an intentional clean lab rebuild:

.. code:: sh

   make destroy
   make up
   make configure
   make verify
   make drift-check
   make integration

Never delete the ownership manifest to bypass a conflict. Unexpected same-name UUIDs, altered domain disk/network paths or unknown pool volumes are fail-closed conditions requiring investigation. Only the exact project pool may be inspected/repaired; do not clean shared /var/lib/libvirt/images or other projects.

Evidence and drills
-------------------

``make demo DEMO=drift|maintenance|abort|invalid`` runs named simulated incidents/exercises. ``make demo`` runs all four. Drills restore and assert health, while normal maintenance preserves failure exclusion for operator recovery. Review JSON and raw JSONL under evidence, including any failures; no-sample or failed checks never imply availability. Repeated runs archive previous probe/report artifacts.

Run configuration, repair, maintenance, rejoin and lifecycle commands sequentially. Concurrent operational invocations are outside this lab's supported workflow; the continuous read-only HTTP probe is the intended exception.
