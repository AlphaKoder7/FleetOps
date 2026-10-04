# FleetOps execution contract
Read FLEETOPS_PLAN.md, AGENTS.md and STATUS.md before resuming. The plan is the specification; do not mark acceptance gates complete without evidence.

- Work only in /home/abini/Projects/FleetOps and recorded project-owned resources. Never read or alter DevOps Lab, its checkout, state, containers, Kubernetes contexts, credentials or AWS resources.
- Use exact fleetops- resource names and recorded ownership. Never run broad cleanup, stop unrelated services, flush firewalls, reboot the host, or restart Docker/libvirt globally.
- Manage only the three Ubuntu 24.04 guests. Never substitute localhost or containers for VM/systemd/reboot coverage. Do not use the GPU.
- Use a dedicated fleetops-net NAT network, detect route/network conflicts, discover guest IPs, and restrict guest access to the lab network.
- Python dependencies belong in .venv; consult official documentation and record installed versions. Never install globally.
- Use an untracked dedicated SSH key and project known-hosts file. Do not disable host-key checks globally or edit user SSH configuration.
- Prefer Ansible modules, roles, templates and handlers; document shell exceptions. Validate candidate configurations before activation.
- Continue routine local implementation and fixes; test each phase before advancing. For sudo or missing input, give the exact user action. Never request/store passwords.
- No external publishing, pushing, contacting people, cloud provisioning or existing credential use. AWS preparation follows verified local completion; applying requires a separately initiated run.
- Update STATUS.md after each phase with actual checks, blockers and next action. Make scoped local Git checkpoints when identity is configured; do not modify global identity.
- Distinguish portable tests from real VM results. Never invent measurements, costs, incidents or completion. Preserve raw observations and report failures honestly.

- Owner authorized read-only local Docker network names/IPAM conflict checks. Pin the local Unix socket; never inspect containers, credentials or network labels, and never alter existing networks.
