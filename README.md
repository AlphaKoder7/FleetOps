# FleetOps

Ansible operations toolkit for a three-VM Ubuntu 24.04 lab: non-root systemd workload, HAProxy, read-only drift detection, targeted repair and health-gated rolling maintenance. [FLEETOPS_PLAN.md](FLEETOPS_PLAN.md) is the specification; [STATUS.md](STATUS.md) records verified completion and remaining checks. Local Phases 0–6 are verified, including scoped teardown/clean rebuild and real-VM integration. AWS provisioning is disabled; Phase 7 preparation/cloud validation remain pending.

## Setup

Use a Linux x86_64 controller with Python 3.12+, Git, Make, KVM/libvirt, cloud-image-utils and virt-install. Initial budget: 3 × 1 vCPU / 1 GiB / 8 GiB sparse guest disks, plus verified base image/cache. Doctor checks available memory and disk before creation. No GPU use, containers or localhost managed-host substitutes.

For missing virtualization packages, run in a host terminal:
```sh
sudo apt-get update
sudo apt-get install qemu-kvm libvirt-daemon-system libvirt-clients virtinst cloud-image-utils cpu-checker python3-venv
sudo usermod -aG libvirt,kvm "$USER"
```
Log out/in, then `kvm-ok` and `virsh -c qemu:///system uri`. Existing sessions can use the configured libvirt group via the script's `sg` subprocess; no password is collected. Do not restart host services globally.

From this checkout:
```sh
make setup
make doctor
make test
make lint
make up
make configure
make verify
make drift-check
```
Run host/guest operations outside restricted sandboxes or authorize access when prompted. Portable tests/lint require no KVM. Python packages stay in .venv; requirements-dev.lock.txt pins the verified environment. First `up` downloads the official HTTPS cloud image and verifies SHA256, checks host routes/libvirt networks/**Docker network IPAM only**, chooses an unused subnet, creates fleetops-net and an ownership-tagged storage pool, then bootstraps management access. No containers, existing networks or DevOps Lab resources are changed. If Docker is installed, local socket access is required for its network conflict check.

The control machine runs Ansible/probes only. HAProxy serves at its discovered guest address on 18080; applications use 18081. Guest firewall rules permit SSH/service traffic only from the lab subnet. SSH keys and pinned host trust are dedicated to this project; guest transport is explicit and unrelated SSH profiles are ignored. IPs are discovered through DHCP, recorded in ignored inventory, and never hardcoded into operational playbooks.

## Operations

| Command | Behavior |
| --- | --- |
| `make doctor` | Read-only host prerequisites, port/routes/libvirt/Docker-IPAM checks |
| `make up` | Create/start recorded fleet; preserve existing UUIDs/disks; discover IPs and wait for cloud-init/SSH |
| `make configure` | Validated baseline/application/HAProxy roles; no metadata refresh in idempotency pass |
| `make verify` | Direct readiness/identity and HAProxy distribution across both nodes |
| `make drift-check` | Explicit managed files/modes/packages/services; JSON plus readable counts |
| `make repair` | Apply supported configuration repair and verify |
| `make maintain` | Drain, patch explicit package set, required reboot, health-gated rejoin; serial application guests only |
| `make maintain OPS_ARGS=--force-reboot` | Explicit lab guest reboot exercise |
| `make demo` | All real guest drills with evidence and health restoration |
| `make demo DEMO=drift` | Modified setting + stopped service; prove detection read-only and repair |
| `make demo DEMO=maintenance` | Rolling forced reboot with continuous HTTP observation |
| `make demo DEMO=abort` | First-node health failure; prove abort/peer preservation; restore demo fleet |
| `make demo DEMO=invalid` | Invalid HAProxy candidate rejection; unchanged active configuration/service |
| `make test` / `make lint` | Portable behavior tests, Python format, Ansible lint/syntax |
| `make integration` | Real guest reachability/health/clean drift/zero-change configuration |
| `make down` | Gracefully stop recorded guests, preserve disks |
| `make destroy` | Verify UUID/pool-path/volume ownership, remove exactly FleetOps resources, verify absence |

Successful checks return 0; drift/probe detected failures return 1; inspection/operational errors return 2. GNU Make itself generally returns 2 for a failed recipe: use `.venv/bin/python scripts/ops.py check` when scripting the drift distinction. Maintenance errors remain nonzero even after rescue; a failed backend stays excluded for recovery. `make repair` does not silently rejoin deliberately excluded backends: see the runbook.

## Verified evidence

Measured rolling reboot: **511 requests, zero observed failures**, p95 **3.22 ms** during the recorded ~102-second window. Each node rebooted; node 1 rejoined before node 2 began. Selected python3-minimal version was unchanged, so no available update is claimed. The deliberate health failure returned 2, preserved node 2, and left node 1 excluded; explicit demo recovery succeeded. These are observed lab windows, not a production availability guarantee.

See [evidence](evidence/README.md), [architecture](docs/architecture.md), [runbook](docs/runbook.md), [managed-state contract](docs/managed-state.md), [maintenance](docs/maintenance.md), [probing](docs/probing.md), [implementation exceptions](docs/implementation-notes.md) and [simulated incidents](docs/incidents). CI runs portable checks only; hosted CI does not claim real KVM integration.

## Isolation and limits

Never delete .runtime/fleet.json before teardown; it is the ownership record. Runtime state/keys, generated inventory, images/disks and Terraform state are untracked. Volumes live only in this project's `fleetops-<UUID>` pool under /var/lib/libvirt/images, created through libvirt. No existing storage/network is adopted. Repeated drills retain previous raw probe/summary artifacts in evidence/history.

Initial scope is Ubuntu 24.04/x86_64 only. The host and load balancer are single points of failure. Short GET observations do not prove long-lived request behavior or arbitrary load. Drift is bounded to documented selected state. There is no automatic package/OS rollback. Loss of the manifest requires careful ownership recovery, not broad cleanup.

AWS code preparation/validation is a separate follow-on; no apply or cloud credentials are used by any local command. DevOps Lab remains isolated.

Official references: [Ubuntu libvirt](https://ubuntu.com/server/docs/how-to/virtualisation/libvirt/), [cloud images](https://cloud-images.ubuntu.com/noble/current/), [Ansible](https://docs.ansible.com/projects/ansible/latest/), [HAProxy socket/stats](https://www.haproxy.org/download/2.8/doc/management.txt).
