Implementation choices
======================

Ansible built-in modules handle packages, users, directories, files, templates, services and reboot. UFW has no module in ansible-core: narrowly scoped guest-only argv commands add the lab-subnet SSH/service rules, set incoming policy only if the configuration differs, and enable UFW only when inactive. Read-only command outputs drive change detection. They never run on the controller. UFW command check-mode predictions are not relied on for drift detection.

The service runs as fleetops-app with no login shell, reads root-owned code/settings, logs to journald and uses systemd restart-on-failure plus filesystem hardening. The baseline also manages operational log rotation. HAProxy configuration and application JSON candidates are validated before atomic installation. HAProxy's administration socket is mode 600 and accessible only to root lab tasks.

Application endpoint portable tests invoke the real handler with an in-memory response stream; they open no host listener and do not stand in for the independently verified real guest endpoints.

HAProxy has no ansible-core runtime-socket module. The root-only lbctl Python helper uses the documented Unix administration socket and CSV stats, with explicit node allowlists and bounded waits. Ansible command argv invokes it only on fleetops-lb. Guest fingerprint commands in the drill driver are read-only Python/systemctl/dpkg queries; SSH shell text uses shlex quoting, never JSON-as-shell escaping. Controller delegation only writes reports/events.

The user explicitly authorized read-only existing Docker network names/IPAM checks. The local Unix Docker socket is pinned; neither containers nor Docker/DevOps Lab state are queried. No existing networks are modified.

Guest inventories explicitly select SSH transport; wrappers force pinned host trust and ignore unrelated user SSH profiles without rewriting them. Run configure/repair/rejoin/lifecycle/maintenance sequentially; concurrent operational invocations are outside the supported workflow.

The explicit package-upgrade demo uses read-only ``apt-cache policy`` and ``dpkg-query`` argv commands on the drained application guest to preserve repository origins and actual installed versions. All package staging/upgrading uses Ansible apt, with exact names/versions, authenticated repositories and removal protection; only the opt-in demo staging task allows a downgrade of unzip.
