# Simulated incident: failed maintenance readiness gate

Scope: intentional FleetOps first-node fault during a lab rolling reboot, not a production incident. [Summary/events/state proof](../../evidence/maintenance-abort.json), [raw HTTP observations](../../evidence/maintenance-abort.jsonl).

Symptoms: after fleetops-web-1 was drained, patched and rebooted, the drill stopped its application service. Direct readiness failed; maintenance returned 2 and left that backend MAINT. fleetops-web-2 stayed UP.

| Observed UTC boundary | Event |
| --- | --- |
| 2026-10-04T18:53:36Z | First node maintenance started |
| 2026-10-04T18:53:40Z | Backend excluded and active/queued requests drained |
| 2026-10-04T18:53:52Z | Actual package versions recorded |
| 2026-10-04T18:54:59Z | Fatal gate/failure boundary preserved |
| 2026-10-04T18:56:38.071614+00:00 | Explicit demo recovery and final fleet verification completed |

Diagnosis: this was an injected stopped-service fault, not an inferred package regression. Selected python3-minimal before/after versions were unchanged. No maintenance event was created for node 2; its boot ID, config hash, package version, service state and apt metadata timestamps matched before/after the failed run.

Fix: explicit configuration restored node 1's workload, direct readiness was required before socket rejoin, HAProxy UP was verified, then fleet health/distribution passed. Normal `make maintain` does not silently perform this demo restoration; the runbook specifies operator recovery.

Measured impact: 818 requests with 0 observed failures; p95 5.35 ms during 2026-10-04T18:53:29.128276+00:00 through 2026-10-04T18:56:12.609470+00:00, including recovery. Healthy node 2 served while node 1 was excluded. This observation does not guarantee production zero downtime or long-lived request behavior.

Prevention: serial batches, alternate-node preflight, bounded drain/readiness gates, explicit fatal failure after rescue, and backend exclusion until verified recovery. Package/OS rollback remains a separate manual recovery decision.
