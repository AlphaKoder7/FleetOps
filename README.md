# FleetOps
Linux configuration, drift recovery and rolling maintenance lab. FLEETOPS_PLAN.md is the specification; STATUS.md records verified progress. Currently Phase 0 only: no guest fleet or AWS resources exist.

## Local prerequisites
Pop!_OS/Ubuntu, Python 3.12+, Git, Make, QEMU/KVM, libvirt, cloud-image-utils and virt-install. Use qemu:///system and a dedicated fleetops-net; never reuse another project's resources.

Run these host commands yourself if virtualization tools are missing:
```sh
sudo apt-get update
sudo apt-get install qemu-kvm libvirt-daemon-system libvirt-clients virtinst cloud-image-utils cpu-checker python3-venv
sudo usermod -aG libvirt,kvm "$USER"
```
Log out and back in to activate group membership, then run `kvm-ok` and `virsh -c qemu:///system uri`. Do not restart host services globally. If libvirt remains unavailable, diagnose its socket activation before continuing.

```sh
make setup
make test
make doctor
```
Doctor is read-only and requires host access to devices, routes and sockets. Under a restricted sandbox, run it from your terminal or authorize host inspection. Exit 0 means prerequisites passed; exit 2 means blocked or inspection incomplete. Future drift checks reserve exit 1 for detected drift, 2 for execution errors. Unimplemented operational targets fail explicitly without mutation.

Python dependencies stay in .venv; requirements-dev.lock.txt records the verified installed environment. Generated state, keys, inventory and disks remain untracked. The doctor avoids Docker APIs and credentials; visible host bridge routes are checked, while inactive/custom Docker networks require an operator-provided subnet list before network creation.

References: [Ubuntu libvirt](https://ubuntu.com/server/docs/how-to/virtualisation/libvirt/), [Ansible support matrix](https://docs.ansible.com/projects/ansible/latest/reference_appendices/release_and_maintenance.html).
