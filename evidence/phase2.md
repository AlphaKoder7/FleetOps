# Phase 2 — real configuration checks

Direct `/health` on both application guests passed, identifying the expected node. Ten HAProxy requests identified both fleetops-web-1 and fleetops-web-2. Ansible reboot module changed fleetops-web-1 boot ID; `/health` recovered afterward.

Second configuration run, without metadata refresh:
```text
fleetops-lb:    changed=0 unreachable=0 failed=0
fleetops-web-1: changed=0 unreachable=0 failed=0
fleetops-web-2: changed=0 unreachable=0 failed=0
```

Ansible lint passed its production profile for the implemented roles/playbooks; 11 portable tests passed separately. No availability measurement is claimed for this phase.
