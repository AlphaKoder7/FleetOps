# FleetOps local lifecycle

`make up` checks host routes, all libvirt network ranges and Docker **network IPAM only**, then selects an unused /24. Docker inspection was explicitly authorized by the owner; no containers are queried. Only read-only local Docker network names/IPAM inspection is allowed; no container or credential inspection.

Three Ubuntu 24.04 KVM guests use 1 vCPU, 1 GiB and an 8 GiB qcow2 overlay each. The official HTTPS image is SHA256-verified. All volumes live in a dedicated `fleetops-<ownership UUID>` libvirt pool under `/var/lib/libvirt/images`. libvirt creates that project-owned storage through its API; no host sudo or global service restart is needed. Cached downloads and seed/SSH material live in ignored `.runtime` (700; private keys 600).

`make down` gracefully stops only the recorded domain UUIDs; disks remain. `make up` starts them and rediscovers DHCP addresses. `make destroy` checks every recorded UUID and pool path, rejects unknown volumes, then deletes only the recorded guests/network/pool and verifies absence. It retains local downloads and SSH keys. Never delete `.runtime/fleet.json` before teardown: it proves ownership. Missing/foreign manifests fail closed. Do not run lifecycle commands concurrently.

SSH host keys are generated locally, injected by cloud-init, and pinned to each discovered guest address in `.runtime/known_hosts`; no global host-key checking changes or SSH configuration edits. Cloud-init installs Python and guest-agent management prerequisites, leaving application configuration to Ansible. Readiness waits are bounded. A failed creation leaves the manifest for scoped recovery/retry.

If group changes are not active in an existing session, commands use `sg libvirt` only when the user is already listed in that group. No membership is changed and no password is requested.
