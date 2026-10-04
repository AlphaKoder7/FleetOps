# Implementation choices

Ansible built-in modules handle packages, users, directories, files, templates, services and reboot. UFW has no module in ansible-core: narrowly scoped guest-only argv commands add the lab-subnet SSH/service rules, set incoming policy only if the configuration differs, and enable UFW only when inactive. Read-only command outputs drive change detection. They never run on the controller. UFW command check-mode predictions are not relied on for drift detection.

The service runs as fleetops-app with no login shell, reads root-owned code/settings, logs to journald and uses systemd restart-on-failure plus filesystem hardening. The baseline also manages operational log rotation. HAProxy configuration and application JSON candidates are validated before atomic installation. HAProxy's administration socket is mode 600 and accessible only to root lab tasks.

Application endpoint portable tests invoke the real handler with an in-memory response stream; they open no host listener and do not stand in for the independently verified real guest endpoints.
