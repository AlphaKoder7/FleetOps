"""Portable Python/Ansible checks; never creates or connects to guests."""

import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    runtime = ROOT / ".runtime"
    runtime.mkdir(exist_ok=True)
    env = os.environ.copy()
    env.update(
        ANSIBLE_CONFIG=str(ROOT / "ansible/ansible.cfg"),
        ANSIBLE_HOME=str(runtime / "ansible-home"),
        ANSIBLE_LOCAL_TEMP=str(runtime / "ansible-tmp"),
        XDG_CACHE_HOME=str(runtime / "cache"),
    )
    env["BLACK_CACHE_DIR"] = str(runtime / "black-cache")
    python_files = sorted(
        path
        for folder in ("app", "scripts", "tests")
        for path in (ROOT / folder).rglob("*.py")
    )
    for path in python_files:
        result = subprocess.run(
            [sys.executable, "-m", "black", "--check", str(path)],
            env=env,
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if result.returncode:
            print(result.stderr)
            return result.returncode
    print(f"Python format: {len(python_files)} files passed", flush=True)
    commands = [[str(ROOT / ".venv/bin/ansible-lint"), "--offline", "ansible"]]
    for playbook in sorted((ROOT / "ansible/playbooks").glob("*.yml")):
        commands.append(
            [
                str(ROOT / ".venv/bin/ansible-playbook"),
                "-i",
                str(ROOT / "ansible/inventories/local/hosts.example.yml"),
                "--syntax-check",
                str(playbook),
            ]
        )
    for command in commands:
        result = subprocess.run(command, env=env, cwd=ROOT)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
