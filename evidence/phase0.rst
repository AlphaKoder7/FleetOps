.. _phase-0-inspection--2026-10-04:

Phase 0 inspection — 2026-10-04
===============================

Actual host execution of ``scripts/doctor.py --json`` returned 2 (prerequisites blocked), with KVM device access passing. Python 3.12.3; roughly 9.5 GiB available RAM and 39.9 GiB free disk. Route and TCP listener queries succeeded; neither lab port was occupied. Virtualization CLI packages are absent and libvirt network inspection is pending installation.

``make test``: five portable unit tests passed. These validate preflight parsing/selection behavior only, not a real VM lifecycle or service. No guests, networks or cloud resources were created. Personal host routes and identity are omitted; raw inspection remains in ignored .runtime.
