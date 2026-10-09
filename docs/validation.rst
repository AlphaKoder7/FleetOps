Validation and release gates
============================

``make test`` runs portable unit/behavior checks for workload readiness/identity/error endpoints, config validation, route/subnet and memory parsing, ownership guards, HAProxy CSV parsing, drift report completeness, probe error counting/p95, event duration calculation and acceptance log parsing. Recorded raw probe summaries are recomputed, with peer-only serving verified inside observed drain/recovery intervals.

``make lint`` checks all project Python files, Ansible lint and syntax for every operational playbook against the example inventory. All caches stay under .runtime. The formatter is invoked one file at a time for deterministic execution. A syntax check does not execute managed-host tasks or validate runtime behavior.

GitHub Actions uses the current official `checkout <https://github.com/actions/checkout>`__ and `setup-python <https://github.com/actions/setup-python>`__ v7 interfaces, Python 3.12, ``contents: read`` and no persisted checkout credentials. CI runs setup, tests and linting; real-VM acceptance runs separately on a KVM-capable host and is captured in the evidence artifacts.

``make integration`` targets only recorded real guests: ping, health/distribution, explicit clean drift, zero-change configuration recap, then health/clean drift again. It requires an already configured healthy fleet; first run ``make up`` / ``make configure`` after a new build. ``make demo`` performs the four original intentional real guest exercises and restores/asserts the lab. ``make demo DEMO=package-upgrade`` separately demonstrates an actual pinned Ubuntu package upgrade plus guest reboots under continuous HTTP probing; evidence tests verify both versions, repository origins, serial boundaries and peer serving. Hosted CI is not assumed to provide KVM.

Lifecycle integration includes real repeat creation, graceful stop/start, ownership-checked teardown with verified absence and clean rebuild with new domain/network/pool UUIDs. Logical operational changes need real guest validation; portable mocks never count as that acceptance gate. Completed local checks are recorded in the evidence directory.
