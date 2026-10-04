# FleetOps status

Updated: 2026-10-04. Specification: FLEETOPS_PLAN.md.

## Completed
- Phase 0 acceptance gate passed: inspected existing directory, scaffolded repository, created AGENTS.md, README, Makefile, isolated .venv and dependency lock. Doctor truthfully reports prerequisites; it need not report READY to satisfy this inspection gate.
- `make test`: five portable tests passed (subnet overlap/exhaustion/IPv6, memory parsing, missing-command handling). No VM integration tests have run.
- Real host doctor (`.venv/bin/python scripts/doctor.py --json`): exit 2 as expected. Pop!_OS 24.04, Python 3.12.3, KVM read/write access, approximately 9.5 GiB available RAM / 39.9 GiB free disk; route and TCP listener inspections passed. No 18080/18081 host listeners.
- Installed ansible-core 2.20.9 and ansible-lint 26.9.0 only in .venv; requirements-dev.lock.txt records resolved versions. Official Ansible support matrix confirms Python 3.12 controller compatibility.
- Raw host preflight: ignored `.runtime/doctor-host.json`; sanitized summary: evidence/phase0.md.

## Active phase / blocker
Phase 1 pending. Host lacks virsh, qemu-img, virt-install and cloud-localds. libvirt connection/network inspection cannot pass until installed. No subnet selected; no network/image/key/guest has been created. All later local acceptance gates and cloud validation remain PENDING. Operational Make targets fail with exit 2 until implemented.

User action in a host terminal:
```sh
sudo apt-get update
sudo apt-get install qemu-kvm libvirt-daemon-system libvirt-clients virtinst cloud-image-utils cpu-checker python3-venv
sudo usermod -aG libvirt,kvm "$USER"
```
Log out/in, then:
```sh
cd ~/Projects/FleetOps
kvm-ok
virsh -c qemu:///system uri
make doctor
```
If libvirt does not connect, investigate socket activation rather than globally restarting services. Never supply a password in chat.

## Next action
After prerequisites pass, implement and verify Phase 1 lifecycle against real guests, including exact ownership records, conflict-checked network, checksum-verified image, project SSH trust, readiness timeouts and repeatability. Before creation, account for inactive/custom Docker network subnets through operator-supplied data; do not inspect DevOps Lab containers or credentials.

## Limitations / isolation
- Restricted sandbox hides KVM/netlink/system service information; host verification was separately authorized. Sandbox failures are not host absence evidence.
- No FleetOps VMs are running or have been created. No AWS resources provisioned, credentials read, external publication or Git push. DevOps Lab untouched.
- Empty app/role/playbook directories reserve future structure; they are not implemented deliverables. CI currently runs portable doctor tests only.
