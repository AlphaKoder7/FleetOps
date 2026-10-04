# Verified local evidence

| Artifact | What was actually observed |
| --- | --- |
| phase0.md | Sanitized host prerequisites; original blocker and sandbox distinction |
| phase1.md | Real three-VM SSH/cloud-init/Ansible reachability, repeated up and down/up |
| phase2.md | Direct/LB identity, guest reboot recovery and zero-change second configuration |
| drift-drill.json | Two intentional faults detected read-only, before/after selected snapshots, repair and clean report |
| invalid-candidate.json | Actual HAProxy validator rejection and unchanged active file/process/service observations |
| maintenance-reboot.json + .jsonl | Events, actual package versions, changed guest boot IDs, measured requests and summary |
| maintenance-abort.json + .jsonl | Fatal first-node failure, excluded backend, unchanged peer fingerprint and explicit recovery |
| rebuild.json | Scoped verified teardown and clean replacement resource identity (status inside artifact) |
| final-drift.json | Final rebuilt-fleet explicit managed-state report, all hosts clean |
| check-diff.json | Successful real-guest check/diff simulation with zero predicted changes |
| local-integration.json | Real fleet health, clean drift and zero-change final configuration (created only on successful run) |

Portable tests recompute probe summaries from raw JSONL and check peer-only serving inside observed drain/recovery windows. These checks do not themselves create VMs. Local integration/drill logs and ownership/SSH/runtime material stay ignored in .runtime. Simulated incident write-ups are in docs/incidents.

Timings are actual UTC observations, not fabricated portfolio values. Event boundaries have one-second resolution; probe request timestamps/latencies are finer. Zero observed failures is limited to the recorded sampling windows. Package versions did not change in the measured demonstrations; no available upgrade is claimed. Host/LB failure and long-running requests are not proven by short GET probes.

No hosted CI execution, external publishing or AWS validation has occurred. Repeated demonstrations archive their prior summary/raw files in evidence/history. All examples use FleetOps guest identity only; personal host routes/credentials are excluded.
