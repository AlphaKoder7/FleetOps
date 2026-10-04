# Drift contract

`make drift-check` performs explicit read-only guest inspections, writes controller observations to `.runtime/drift`, and returns 0 (clean), 1 (drift) or 2 (execution/incomplete-report error). `make repair` applies the configuration roles then verifies readiness and distribution. There is no automatic package/OS rollback.

Selected managed state:

| Hosts | Files (root:root, 0644; SHA256 of desired content) | Packages present | Service enabled/running |
| --- | --- | --- | --- |
| All | `/etc/logrotate.d/fleetops` | python3, ufw, logrotate | Per-role service below |
| Application nodes | `/opt/fleetops/server.py`, `/etc/fleetops/application.json`, `/etc/systemd/system/fleetops-app.service` | Baseline above | fleetops-app.service |
| Load balancer | `/etc/haproxy/haproxy.cfg`, `/opt/fleetops/lbctl.py` | Baseline plus haproxy | haproxy.service |

The checker uses stat checksums/permissions, package facts and service facts. It does not run configuration roles, handlers, firewall commands, package metadata refresh or service restarts. Writing observations with controller delegation is not a managed-host fallback. Missing/unreachable guest reports are operational errors, never clean results. Report files are recreated each run to prevent stale observations.

Supported `configure --check --diff` is an additional simulation; it is not the drift acceptance gate because command tasks, runtime services and conditionals have limitations. Firewall rules, user metadata, directory state and intentional HAProxy backend exclusions are outside this bounded drift contract; verify/maintenance provide separate health gates.
