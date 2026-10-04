Simulated incident: setting drift and stopped service
=====================================================

Scope: intentional guest-only FleetOps drill, not a production incident. `Measured observations <../../evidence/drift-drill.json>`__.

Symptoms: a managed application version setting was changed on fleetops-web-1 without restarting it; fleetops-web-2's service was stopped. The read-only checker identified the file-content drift and stopped service, returning 1. There was no continuous HTTP probe for this drift exercise, so no availability percentage is claimed.

+----------------------------------+------------------------------------------------------+
| Observed UTC boundary            | Event                                                |
+==================================+======================================================+
| 2026-10-04T18:40:50.186263+00:00 | Drill began with healthy fleet verification          |
+----------------------------------+------------------------------------------------------+
| 2026-10-04T18:41:50.946377+00:00 | Per-host drift observations aggregated               |
+----------------------------------+------------------------------------------------------+
| 2026-10-04T18:43:34.290167+00:00 | Repair/health verification and clean check completed |
+----------------------------------+------------------------------------------------------+

Diagnosis: selected file SHA256 differed from the desired rendered settings; service facts reported the second workload stopped while enabled. Before/after detection snapshots matched file hash/mode/mtime and service status/restart counter on both application nodes. Detection therefore did not perform the repair.

Fix: the configuration roles restored the setting and started the stopped workload; health and distribution verification passed, followed by a clean report with zero findings on all three guests.

Prevention: keep desired settings in Ansible, validate candidates before activation, run the explicit checker, and keep detection separate from repair. This bounded checker covers documented files/packages/services; it does not assert every aspect of guest state.
