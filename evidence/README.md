# Verified local evidence

| Artifact | What was actually observed |
| --- | --- |
| phase0.md | Sanitized host prerequisites; original blocker and sandbox distinction |
| phase1.md | Real three-VM SSH/cloud-init/Ansible reachability, repeated up and down/up |
| phase2.md | Direct/LB identity, guest reboot recovery and zero-change second configuration |
| drift-drill.json | Two intentional faults detected read-only, before/after selected snapshots, repair and clean report |
| invalid-candidate.json | Actual HAProxy validator rejection and unchanged active file/process/service observations |
| maintenance-reboot.json + .jsonl | Events, actual package versions, changed guest boot IDs, measured requests and summary |
| maintenance-package-upgrade.json + .jsonl | Actual unzip release-to-security upgrade on both guests; repository origins, before/after dpkg versions, serial drain/reboot/rejoin and 678 raw HTTP observations |
| maintenance-validation.json | Post-change portable/lint checks, real-VM integration and final clean drift after the actual upgrade |
| maintenance-abort.json + .jsonl | Fatal first-node failure, excluded backend, unchanged peer fingerprint and explicit recovery |
| rebuild.json | Scoped verified teardown and clean replacement resource identity (status inside artifact) |
| final-drift.json | Final rebuilt-fleet explicit managed-state report, all hosts clean |
| check-diff.json | Successful real-guest check/diff simulation with zero predicted changes |
| local-integration.json | Real fleet health, clean drift and zero-change final configuration (created only on successful run) |

Portable tests recompute probe summaries from raw JSONL and check peer-only serving inside observed drain/recovery windows. These checks do not themselves create VMs. Local integration/drill logs and ownership/SSH/runtime material stay ignored in .runtime. Simulated incident write-ups are in docs/incidents.

Timings are actual UTC observations, not fabricated portfolio values. Event boundaries have one-second resolution; probe request timestamps/latencies are finer. Zero observed failures is limited to the recorded sampling windows. The original reboot/abort demonstrations recorded unchanged python3-minimal versions. The separate package-upgrade demo deliberately stages unzip 6.0-28ubuntu4, then actually upgrades to 6.0-28ubuntu4.1 on each drained guest; it records 678 requests, 0 observed failures and p95 4.74 ms. This is controlled lab setup, not a naturally pending production update. Host/LB failure and long-running requests are not proven by short GET probes.

Public GitHub publication was explicitly authorized after reviewing tracked files and history (publication-review.md). Local results are verified; hosted CI results must be checked in GitHub Actions. AWS validation remains pending and provisioning disabled. Repeated demonstrations archive their prior summary/raw files in evidence/history. All examples use FleetOps guest identity only; personal host routes/credentials are excluded.
