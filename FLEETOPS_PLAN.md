# FleetOps: Linux Configuration, Patching and Drift Recovery

Project owner: Abin Issac | GitHub: AlphaKoder7

Status: PLANNED. This document is a specification, not evidence of completed work.

## 1. Goal and career fit

Build an operations toolkit that configures a small Linux server fleet, detects configuration drift, repairs defined faults, and performs rolling maintenance with health checks and an audit trail.

The portfolio gap this fills is Linux configuration management and server maintenance. Phoenix Protocol demonstrates Azure SQL drill automation. DevOps Lab demonstrates infrastructure provisioning and application delivery through AWS, Kubernetes and Helm, with observability and recovery in its intended scope. Simulation Job Queue already includes application metrics and a Prometheus/Grafana setup.

FleetOps adds Ansible, systemd operations, controlled patching, load-balancer coordination, configuration validation, and repeatable operational evidence. Target roles remain junior DevOps, SRE, Cloud Infrastructure, Platform and CloudOps.

Success means a reviewer can reproduce the lab, break a defined configuration, detect and repair the fault, and observe a rolling maintenance run with actual availability measurements.

## 2. Bounded scope

### Required local deliverable

- Three real Ubuntu 24.04 LTS VMs: one load balancer and two application nodes.
- Reproducible VM creation and teardown.
- Ansible roles for Linux baseline, application service and load balancer.
- Idempotent configuration with a verified second-run result.
- Read-only drift reporting plus a separate repair operation.
- One-node-at-a-time maintenance, including an explicit reboot exercise.
- Continuous HTTP probing, machine-readable reports and failure demonstrations.
- CI checks, setup documentation, a runbook and two short incident write-ups.

### Follow-on cloud validation

Provision the same topology briefly on AWS using Terraform and reuse the Ansible roles. Prepare the cloud implementation and documentation after the local lab works. Actual AWS creation is a separately initiated run because it uses an account and incurs charges. Local completion does not imply cloud validation is complete.

### Excluded from the initial build

Kubernetes, an AI remediation agent, a web dashboard, Backstage, a database, a message broker, multi-cloud support and multi-distribution support. The application exists only to demonstrate operations. Avoid growing it into a backend product.

## 3. Architecture and implementation decisions

| Component | Decision | Purpose |
| --- | --- | --- |
| Control machine | Existing Pop!_OS laptop | Runs Codex, Ansible, scripts and probes |
| Local virtualization | QEMU/KVM with libvirt and cloud-init | Real boot, reboot, systemd and package-management behaviour |
| VM OS | Ubuntu 24.04 LTS cloud image | Consistent first implementation |
| Load balancer | HAProxy on `fleetops-lb` | Health checking and explicit backend drain/rejoin |
| Application | Tiny Python HTTP service on `fleetops-web-1` and `fleetops-web-2` | Returns health, node identity and version |
| Service manager | systemd | Non-root service, restart behaviour and journald logs |
| Configuration management | Ansible | Reusable roles and operational playbooks |
| Supporting automation | Python and small Bash scripts | VM lifecycle, probing and reports |
| CI | GitHub Actions | Lint, syntax checks and meaningful portable tests |
| Cloud follow-on | AWS EC2 and Terraform | Reproduce the fleet outside the laptop |

Use a dedicated libvirt NAT network named `fleetops-net`. Detect subnet conflicts with existing host routes, Docker networks and libvirt networks before choosing its address range. Do not reuse or modify an existing network. Discover VM addresses rather than hardcoding a subnet throughout the code.

Start with 1 vCPU, 1 GiB RAM and an 8 GiB sparse disk per VM, plus one downloaded base image. These are starting allocations, not guaranteed requirements. Check actual RAM, disk and virtualization availability first; report resource limits before starting the VMs. Do not use the NVIDIA GPU.

The host probes HAProxy at its private VM IP on port 18080. Application nodes listen on port 18081. Restrict access to the lab network; do not expose the lab to the public internet. The host is the Ansible controller and does not run an application server or load balancer.

The HTTP application exposes:

- `/health`: returns 200 only when ready.
- `/`: returns JSON containing node name and application version.

Keep the service stateless, small and dependency-light. Returning node identity makes distribution and node exclusion observable.

## 4. Isolation and execution rules for Codex

1. Work within `~/Projects/FleetOps` and project-owned VM/storage resources. Inspect the actual current directory before making changes.
2. Do not read or change DevOps Lab, its Git checkout, Terraform state, AWS resources, containers, Kubernetes contexts or credentials.
3. Use `fleetops-` names for VMs, storage and generated resources. Validate exact names and recorded ownership before teardown; never issue broad host cleanup commands.
4. Check for existing processes and port/network conflicts. Do not stop unrelated services, flush firewall rules, reboot the host or restart Docker/libvirt globally.
5. Run operating-system baseline and patching playbooks against the FleetOps guests only. Never use localhost as a fallback managed host.
6. Keep Python dependencies in `.venv`. Select compatible current versions, record them, and verify commands against current official documentation. Avoid global pip installs.
7. Create a dedicated SSH key for these lab VMs. Keep it untracked, with appropriate permissions. Maintain a project-specific known-hosts file; do not globally disable host-key checking or rewrite the user's SSH configuration.
8. Prefer Ansible modules, roles, templates and handlers to unstructured remote shell commands. Document justified exceptions.
9. Continue through routine implementation, local tests and fixes without requesting approval for every phase. If sudo or a missing prerequisite requires user input, give the exact command and continue independent work where possible. Never collect a password in chat or store it in project files.
10. Do not contact people, publish externally, push commits, create cloud infrastructure or use existing cloud credentials merely because this plan mentions those activities. Implement local work first; prepare cloud code without applying it.
11. After each phase, update `STATUS.md` with verified results, remaining work, blockers and the next action. Make local Git checkpoints if the repo and Git identity are ready; do not change global Git identity.
12. Mark an acceptance check complete only when it has actually passed. Distinguish a mock/unit test from a real VM integration run. Never invent uptime, timings, cost, screenshots or incident evidence.

## 5. Repository structure

Use this as a practical starting structure; adjust filenames when implementation warrants it.

```text
FLEETOPS_PLAN.md
AGENTS.md
README.md
STATUS.md
Makefile
requirements-dev.txt
ansible/
  ansible.cfg
  inventories/local/
  group_vars/
  roles/baseline/
  roles/application/
  roles/load_balancer/
  playbooks/configure.yml
  playbooks/check.yml
  playbooks/repair.yml
  playbooks/maintain.yml
  playbooks/verify.yml
app/
scripts/
tests/
infra/local/
infra/aws/
docs/architecture.md
docs/runbook.md
docs/incidents/
evidence/
.github/workflows/ci.yml
```

Ignore `.venv`, private keys, generated inventories with sensitive paths, VM disks/images, raw local state, credentials, Terraform state and temporary runtime files. Keep sanitized example inventory and representative evidence suitable for Git. Do not include credentials or unneeded personal host details in evidence.

## 6. Build phases and acceptance gates

### Phase 0: Inspect and scaffold

- Read this plan and inspect the existing FleetOps directory without overwriting files.
- Check OS, Python, Git, free disk/RAM, `/dev/kvm`, libvirt availability, permissions, ports and routes.
- Select a compatible virtualization setup from the intended KVM/libvirt approach. If KVM is unavailable, document the blocker; do not silently substitute containers and claim reboot/systemd coverage.
- Create `AGENTS.md` carrying the execution rules above; create README, STATUS, dependency definitions and basic project commands.
- Implement `make doctor` as a read-only preflight check with useful errors and next steps.

Gate: doctor reports real prerequisite status, the repo is organized, and no guests or cloud resources have been created by scaffolding alone.

### Phase 1: Reproducible local fleet

- Download the official Ubuntu cloud image with checksum verification.
- Use cloud-init only for bootstrapping management access and prerequisites; leave the service configuration to Ansible.
- Create the dedicated network, three VMs and generated inventory.
- Wait for cloud-init and SSH readiness with timeouts.
- Make creation repeatable: preserve existing healthy FleetOps VMs instead of duplicating them.
- Provide scoped stop, start and destroy commands with exact ownership checks.

Gate: all three VMs are reachable through Ansible; a second creation run does not duplicate resources; stop/start works. Verify a clean rebuild when convenient before final delivery.

### Phase 2: Baseline and working service

- Configure the required users, directories, permissions, packages and log rotation.
- Install the Python workload as a non-root systemd service with restart behaviour and logs.
- Configure HAProxy health checks, backend routing and a local administration socket accessible only to the intended privileged lab tasks.
- Validate candidate configuration before replacement/reload.
- Enable services to start after reboot.
- Manage guest access rules while preserving Ansible management access.

Gate: both application nodes respond directly; requests through HAProxy identify both nodes; VM reboot restores services; a second baseline configuration run records zero unnecessary managed-state changes. Separate package metadata refresh from the idempotency assertion.

### Phase 3: Drift detection and targeted repair

- Define an explicit managed-state inventory: selected file contents/modes, service enabled/running status and required package presence.
- Detect those states with read-only checks and supported Ansible check/diff behaviour. Do not assume check mode covers every task or module.
- Emit per-host findings and an aggregate status in JSON and readable text.
- Make drift reporting separate from repair. Detection must not restart a service or overwrite a file.
- Use scoped configuration roles/playbooks to repair supported drift, then verify recovery.

Gate: modify one managed application setting and stop one service in the guests. The checker identifies both faults without changing them; repair restores desired state; a subsequent check is clean. Verify file and service state before and after detection.

### Phase 4: Rolling maintenance

- Run maintenance with one application node per batch.
- Preflight fleet health and ensure the other node can serve before draining a backend.
- Put the selected backend into maintenance/drain state; wait for active requests to finish, with a timeout.
- Refresh package metadata and upgrade only an explicitly configured package set. Record selected packages and actual before/after versions. If no update is available, report that truthfully.
- Reboot only when required, or use an explicit lab-only forced reboot option for demonstration.
- Wait for management connectivity, direct application readiness and load-balancer health before rejoining.
- Proceed to the next node only after all gates pass.
- If an update or health check fails, stop the overall run, leave the failed backend excluded, preserve the healthy node and record how to recover. Do not mask failure with a successful rescue block.
- Keep the load-balancer VM outside the rolling application-node maintenance target.

Gate: node 1 completes before node 2 starts; the healthy node serves throughout the exercise; a deliberate first-node health failure prevents maintenance on node 2. Verify the failing command returns nonzero. Do not promise automatic OS/package rollback; known-good configuration restoration and manual recovery are separate operations.

### Phase 5: Reports and failure demonstrations

- Build a continuous HTTP probe that timestamps requests and records status, latency, returned node and version.
- Record maintenance boundaries and summarize request count, failure count/rate, p95 latency and per-node maintenance/recovery times.
- Preserve raw observations alongside summaries. Define the observation window and timeout so results can be interpreted.
- Exercise configuration drift, a stopped service, an invalid candidate configuration and a failed maintenance health gate.
- Restore the lab after each exercise; assert the final healthy state.

Gate: real evidence demonstrates detection/repair, rejection of invalid configuration, successful rolling reboot and abort-on-failure. Report any request failures without relabeling them as zero downtime. The load balancer and host remain single points of failure in this lab.

### Phase 6: CI, documentation and local release

- CI runs Ansible lint/syntax checks, Python checks and tests for actual parser/report/probe behaviour and relevant workload endpoints.
- Validate changed operational logic against real local VMs. A hosted CI runner is not assumed to provide KVM; label the local integration suite clearly.
- Document setup, start/stop/destroy, configuration, drift check/repair and maintenance.
- Write a runbook covering unreachable guests, bad configuration, drained backends and recovery after a failed maintenance run.
- Write two incident reports from observed drills: symptoms, timeline, diagnosis, fix and prevention. Label them simulated incidents.
- Update STATUS and README to describe implemented behaviour and remaining limitations honestly.

Gate: commands can reproduce the workflow from the README; meaningful checks pass; two drill write-ups and sanitized measured evidence exist; teardown targets only FleetOps resources.

### Phase 7: AWS validation preparation and later execution

- Add Terraform for an isolated, tagged FleetOps VPC and three Ubuntu EC2 instances. Use project-owned state and credentials configuration; do not reuse DevOps Lab state.
- Use small configurable instance sizes; determine actual regional availability and estimated compute, disk and public IPv4 charges before proposing a run.
- For a short demo, public subnets may be used with restrictive security groups: SSH only from a specified operator IP, application access only from the load-balancer security group, and HAProxy demo access only from the operator IP. Document that this is a cost-conscious demo topology rather than a production private-subnet design.
- Generate inventory from Terraform outputs and reuse configuration/maintenance roles.
- Include validate/plan, apply, configuration, verification and scoped destroy instructions. Avoid adding NAT gateways or managed load balancers solely for this demo.
- Prepare code without provisioning. When the user explicitly initiates the cloud run, perform the same acceptance checks and teardown, then verify no project resources remain. Destroy can fail; a cleanup command is not proof of successful cleanup.

Gate: code validation and documentation may pass before execution, but AWS deployment/recovery/cost evidence stays PENDING until a real run occurs.

## 7. Intended command interface

These targets are requirements to implement; they are not commands that exist yet.

| Command | Behaviour |
| --- | --- |
| `make doctor` | Read-only prerequisite and conflict checks |
| `make up` | Create/start this project's local VMs and inventory |
| `make configure` | Apply baseline, service and load balancer roles |
| `make verify` | Assert current fleet and service health |
| `make drift-check` | Report managed-state drift without mutation |
| `make repair` | Repair supported drift and verify |
| `make maintain` | Roll through application nodes with health gates |
| `make demo` | Run named guest-only demonstrations and collect evidence |
| `make test` | Portable meaningful checks |
| `make integration` | Real-VM integration checks |
| `make down` | Stop FleetOps VMs and preserve disks |
| `make destroy` | Remove exactly the recorded FleetOps local resources |

Use documented exit statuses: successful checks return 0; detected drift returns a distinguishable nonzero status; operational errors return a separate nonzero status. Do not confuse expected drift detection with an execution error. Commands that mutate state should be named plainly.

## 8. Definition of done

- [ ] Dedicated three-VM fleet is reproducible.
- [ ] Configuration is modular and verified idempotent.
- [ ] Non-root systemd workload survives guest reboot.
- [ ] Load balancing and node identity are observable.
- [ ] Drift reporting is read-only and repair is verified.
- [ ] Invalid configuration is rejected before replacing active configuration.
- [ ] Rolling maintenance drains, patches, reboots, checks and rejoins one node at a time.
- [ ] First-node failure prevents changes to the next node.
- [ ] Reports contain actual timestamps, request observations and measurements.
- [ ] CI checks and local integration checks are honestly distinguished.
- [ ] Runbook and two simulated incident reports are complete.
- [ ] Scoped stop, start, rebuild and teardown are verified.
- [ ] README and STATUS distinguish completed local work from pending AWS work.

Only after verification, write resume bullets using actual results. A possible structure is: "Built Ansible automation for a three-node Linux lab, with drift detection, targeted repair and health-gated rolling maintenance; measured [observed result] during [defined exercise]." Replace placeholders with evidence; do not claim production experience or arbitrary scale.

## 9. Codex working loop and handoff

Treat this plan as the project specification. Begin with Phase 0, then proceed through the required local phases sequentially, resolving failures before advancing. Do not pause simply because a phase ended. Pause only for an actual prerequisite requiring user action, a material conflict with this plan, or an explicitly initiated external action not yet authorized.

Keep `STATUS.md` concise:

- Completed phases and verified evidence/commands.
- Active phase and pending acceptance checks.
- Actual blockers and precise user action if needed.
- Next step and relevant local artifacts.
- Known limitations and pending cloud validation.

Before ending a working session, provide a short account of what works, what was actually tested, which VMs are running, and the next command. A future Codex session should read FLEETOPS_PLAN.md, AGENTS.md and STATUS.md before resuming.

## 10. Official references for implementation

Consult current documentation when selecting versions and implementing behaviours:

- Ansible playbooks and idempotency: https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_intro.html
- Check/diff mode limitations: https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_checkmode.html
- Execution strategies and serial batches: https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_strategies.html
- Delegation and load-balancer coordination: https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_delegation.html
- Error handling: https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_error_handling.html
- Ubuntu libvirt/KVM: https://ubuntu.com/server/docs/how-to/virtualisation/libvirt/
- Ubuntu cloud images: https://cloud-images.ubuntu.com/noble/current/
- cloud-init: https://cloudinit.readthedocs.io/en/latest/
- HAProxy documentation: https://www.haproxy.org/#docs
- systemd service configuration: https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html
- AWS Terraform provider: https://registry.terraform.io/providers/hashicorp/aws/latest/docs

Do not rely on a reference link alone as proof that the local implementation works. Real checks and reports supply that evidence.
