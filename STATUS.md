# FleetOps status

Updated: 2026-10-05 (Asia/Kolkata). Read FLEETOPS_PLAN.md and AGENTS.md before resuming.

## Verified local phases

| Phase | Actual acceptance results |
| --- | --- |
| 0 | Scaffold and read-only doctor; current host doctor returns 0. Pop!_OS 24.04 / Python 3.12.3 / KVM/libvirt; final inspection ~6.3 GiB available RAM, 36.4 GiB free disk. |
| 1 | Three real Ubuntu 24.04 guests, official SHA256-verified image, conflict-checked dedicated NAT/pool, pinned SSH/cloud-init/Ansible readiness. Repeated up preserves UUIDs/disks; graceful down/up passed. Exact teardown verified old resources absent; clean rebuild has new domain/network/pool UUIDs. |
| 2 | Baseline, non-root systemd workload and HAProxy roles; validated candidates, restricted guest ingress, direct/LB identity, actual non-root process UID and root-owned 0600 administration socket verified. Real guest reboot recovery passed. Final configuration changed=0 / failed=0 / unreachable=0 on all three. |
| 3 | Modified node 1 setting plus stopped node 2 service detected (exit 1). Before/after file/service snapshots matched: detection did not repair. Separate repair/health verification succeeded; clean check returned 0. |
| 4 | Serial forced reboot of both app guests; node 1 rejoined before node 2 began. Original python3-minimal version remained 3.12.3-0ubuntu2.1 (no update claimed). Separate actual-upgrade demo on both guests: unzip 6.0-28ubuntu4 → 6.0-28ubuntu4.1, exact dpkg before/after, authenticated Ubuntu repository policy, changed boot IDs and healthy serial rejoin. Deliberate first-node health failure returned 2, left it MAINT, and preserved node 2 boot/config/package/service/apt-metadata fingerprints with no node 2 maintenance events. Explicit demo recovery passed. |
| 5 | Invalid HAProxy candidate: validator exit 1 / wrapper exit 2 / changed=false; active file hash/mode/mtime and MainPID/service unchanged. Real drift/rolling/abort/rejection observations preserved; final fleet healthy/clean. |
| 6 | 25 portable tests pass; Python format, Ansible lint production profile, all playbook syntax checks, workflow YAML and dependency consistency pass locally. Real rebuilt-fleet integration passes. Check/diff simulation returns 0 with zero predicted changes. Runbook and two observed simulated incident reports complete. |

Measured actual package upgrade plus reboot: **678 requests / 0 observed failures / p95 4.74 ms**, UTC window 2026-10-04T19:49:12.838291 through 19:51:28.304125 (~135 s), interval 0.2 s / timeout 2 s. Node maintenance/recovery: 58/21 s and 64/21 s; peer-only successful observations during drain/recovery. Both guests retain the upgraded unzip version. This was deliberately staged lab preparation, not a naturally pending update.

Measured original rolling reboot: 511 requests / 0 observed failures / p95 3.22 ms in the recorded ~102 s window. Node maintenance/recovery: 45/21 s and 43/20 s. Abort/recovery: 818 requests / 0 observed failures / p95 5.35 ms in ~163 s. Short sampled lab windows do not guarantee zero downtime under arbitrary conditions.

## Runtime and artifacts

- Current rebuilt guests: fleetops-lb, fleetops-web-1 and fleetops-web-2 running on fleetops-net (192.168.150.0/24). Addresses/SSH trust are discovered/generated, not source-code constants.
- Ownership and exact UUIDs: ignored `.runtime/fleet.json`; dedicated UUID-named pool under `/var/lib/libvirt/images`. Keep the manifest until successful teardown. `.runtime` is private; keys are untracked with mode 600.
- Evidence: `evidence/{drift-drill,invalid-candidate,maintenance-reboot,maintenance-abort,maintenance-package-upgrade,rebuild,local-integration,check-diff,final-drift}.json`; raw requests in corresponding maintenance `.jsonl`. Raw command logs/snapshots stay in ignored `.runtime`.
- Docs: README.md, docs/runbook.md, docs/managed-state.md, docs/maintenance.md, docs/probing.md, docs/validation.md and docs/incidents/*.md.
- Dependencies: .venv only; ansible-core 2.20.9 / ansible-lint 26.9.0; exact resolved pins in requirements-dev.lock.txt.

## Maintenance validation follow-up

Actual package-upgrade evidence and final demo health verification pass. Reproduce with `make demo DEMO=package-upgrade`; normal maintenance still selects python3-minimal. The opt-in profile stages only unzip while drained (repeat runs explicitly downgrade that demo package), upgrades the exact authenticated Ubuntu security version and fails if pins are unavailable or actual versions do not change. Existing failure/exclusion and serial health gates remain in place. Evidence tests verify exact versions, serial reboots, repository origins and raw request summaries/peer serving. Post-change `make test` (25 passed), `make lint` (format / Ansible production-profile lint / all syntax checks), `make integration` (all six guest checks returned 0; all three configure recaps changed=0 / failed=0 / unreachable=0) and `git diff --check` pass. Latest explicit drift report is clean on all guests; previous integration/drift reports are archived in evidence/history. Local checkpoint follows these verified results.

## Next action and limitations

No local prerequisite/user-action blocker. Next command: `make verify`; use `make down` to conserve RAM while preserving disks. `make integration` expects an already configured healthy fleet; `make demo` reruns real guest drills and restores health.

Phase 7 AWS preparation and cloud validation remain PENDING. No AWS resources provisioned, existing cloud credentials read, external publishing or Git push. Hosted CI workflow is prepared but has not run remotely; local equivalents passed. DevOps Lab untouched except the explicitly authorized read-only Docker network names/IPAM ranges; no containers/labels/credentials inspected and no existing network modified.

The existing session has stale supplemental groups; wrappers activate the already configured libvirt group via sg. Restricted sandboxes hide host sockets/devices/routes; host gates were run with authorized host access. Guest SSH transport/trust is explicit and unrelated user SSH profiles are ignored. Drift coverage is bounded; concurrent operations are unsupported, host/LB are single points of failure, long-lived request drain is unproven, and there is no automatic package/OS rollback. Local release is complete; cloud deployment/recovery/cost evidence remains pending a separately initiated run.
