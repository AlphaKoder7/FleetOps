# FleetOps status

Updated: 2026-10-05. Specification: FLEETOPS_PLAN.md.

## Completed
- Phase 0 acceptance gate passed: inspected existing directory, scaffolded repository, created AGENTS.md, README, Makefile, isolated .venv and dependency lock. Doctor truthfully reports prerequisites; it need not report READY to satisfy this inspection gate.
- `make test`: five portable tests passed (subnet overlap/exhaustion/IPv6, memory parsing, missing-command handling). No VM integration tests have run.
- Real host doctor (`.venv/bin/python scripts/doctor.py --json`): exit 2 as expected. Pop!_OS 24.04, Python 3.12.3, KVM read/write access, approximately 9.5 GiB available RAM / 39.9 GiB free disk; route and TCP listener inspections passed. No 18080/18081 host listeners.
- Installed ansible-core 2.20.9 and ansible-lint 26.9.0 only in .venv; requirements-dev.lock.txt records resolved versions. Official Ansible support matrix confirms Python 3.12 controller compatibility.
- Raw host preflight: ignored `.runtime/doctor-host.json`; sanitized summary: evidence/phase0.md.

## Phase 1 verified
Three real Ubuntu 24.04 KVM guests completed cloud-init and pinned-key SSH readiness. Ansible ping passed for all three before and after a graceful down/up. A second up preserved domain UUIDs and disks without defining new guests. Dedicated subnet: 192.168.150.0/24. Ownership manifest: .runtime/fleet.json. Eight portable tests pass. Clean destroy/rebuild remains a final-delivery check.

## Phase 2 verified
Baseline, non-root systemd application and HAProxy roles configured successfully. Direct readiness/identity and HAProxy distribution checks passed. Real Ansible reboot of fleetops-web-1 changed its boot ID and workload recovered. Second configuration recap: changed=0 / failed=0 / unreachable=0 for all three guests (raw .runtime/configure-second.log; no apt metadata refresh in this assertion). Ansible lint production profile passed; 11 portable tests pass.

## Active phase
Phase 3: read-only managed-state reporting and targeted repair. Three guests are running and healthy. Rolling maintenance/drill/CI/release gates remain pending. AWS provisioning disabled.

## Next action
Implement per-host/aggregate drift reports, demonstrate modified application settings plus stopped service without detection mutation, repair, then verify a clean report. Lifecycle clean teardown/rebuild still pending final delivery.

## Limitations / isolation
- Restricted sandbox hides KVM/netlink/system service information; host verification was separately authorized. Sandbox failures are not host absence evidence.
- Three FleetOps guests have started; guest service configuration is pending. No AWS resources provisioned, credentials read, external publication or Git push. DevOps Lab untouched.
- Empty app/role/playbook directories reserve future structure; they are not implemented deliverables. CI currently runs portable doctor tests only.
