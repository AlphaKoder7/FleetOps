# Phase 1 — real VM checks

Three Ubuntu 24.04 KVM guests (1 vCPU/1 GiB/8 GiB each) completed cloud-init and pinned SSH readiness. Official cloud image SHA256: `6a81c37564db9b1ee84e141922625e1d7c5b389b99bb3c572e0243607d5bb4d2`.

Ansible ping passed on fleetops-lb, fleetops-web-1 and fleetops-web-2. Second `make up` only inspected/started existing recorded resources: no new domain definitions or volumes. `make down` gracefully stopped all three; subsequent `make up` rediscovered addresses and Ansible ping passed again. Eight portable tests pass separately. Clean ownership-checked destroy/rebuild subsequently passed: see rebuild.json and local-integration.json.
