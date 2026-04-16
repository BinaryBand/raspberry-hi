#!/usr/bin/env python3
"""Validate prerequisites before running make site.

Usage:
  poetry run python scripts/check.py             full check
  poetry run python scripts/check.py --vault-only  fast vault-only check (Makefile prereq)
"""

import sys

from utils.ansible_utils import ANSIBLE_DIR
from utils.exec_utils import resolve_executable, run_resolved

VAULT_PASSWORD_FILE = ANSIBLE_DIR / ".vault-password"
MIN_PYTHON = (3, 12)


def check(label: str, ok: bool, fix: str = "") -> bool:
    mark = "OK  " if ok else "FAIL"
    print(f"  [{mark}]  {label}")
    if not ok and fix:
        print(f"          fix: {fix}")
    return ok


def check_vault_secrets() -> bool:
    """Verify the vault is decryptable and all required secrets are present."""
    from bootstrap import SECRETS, decrypt_vault, discover_hosts

    if not VAULT_PASSWORD_FILE.exists():
        return check(
            "Vault secrets complete",
            False,
            "run `make bootstrap` — vault password file is missing",
        )

    secrets = decrypt_vault()

    missing_static = [s["key"] for s in SECRETS if not getattr(secrets, s["key"], None)]

    hosts = discover_hosts()
    become_pwds = secrets.become_passwords or {}
    missing_hosts = [h for h in hosts if not become_pwds.get(h)]

    missing = missing_static + [f"become_passwords.{h}" for h in missing_hosts]
    return check(
        "Vault secrets complete",
        not missing,
        f"run `make bootstrap` to add: {', '.join(missing)}" if missing else "",
    )


def main() -> None:
    vault_only = "--vault-only" in sys.argv

    if vault_only:
        all_ok = check_vault_secrets()
        if not all_ok:
            sys.exit(1)
        return

    print("Checking prerequisites...\n")
    all_ok = True

    # Python version
    py_ok = sys.version_info >= MIN_PYTHON
    min_str = f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]}"
    run_str = f"{sys.version_info.major}.{sys.version_info.minor}"
    all_ok &= check(
        f"Python >= {min_str} (running {run_str})",
        py_ok,
        f"pyenv install {min_str} && pyenv global {min_str}",
    )

    # Ansible reachable
    try:
        resolve_executable("ansible")
        ansible_found = True
    except FileNotFoundError:
        ansible_found = False
    all_ok &= check(
        "ansible available in PATH",
        ansible_found,
        "poetry install  (or: pipx install ansible)",
    )

    # Node.js for make cpd
    try:
        resolve_executable("node")
        node_found = True
    except FileNotFoundError:
        node_found = False
    all_ok &= check(
        "node available in PATH (for make cpd)",
        node_found,
        "install Node.js 18+ via nvm, your distro's package manager, or nodejs.org",
    )

    # Vault password file exists and is private
    vault_ok = VAULT_PASSWORD_FILE.exists() and VAULT_PASSWORD_FILE.stat().st_mode & 0o777 == 0o600
    all_ok &= check(
        "Vault password file exists (ansible/.vault-password, mode 600)",
        vault_ok,
        "echo 'your-password' > ansible/.vault-password && chmod 600 ansible/.vault-password",
    )

    # Vault secrets completeness (only meaningful when the password file exists)
    if vault_ok:
        all_ok &= check_vault_secrets()

    # Pi reachable
    inventory_path = ANSIBLE_DIR / "inventory" / "hosts.ini"

    ping = run_resolved(
        ["ansible", "devices", "-m", "ping", "-i", str(inventory_path)],
        capture_output=True,
        text=True,
    )
    pi_ok = "SUCCESS" in ping.stdout
    all_ok &= check(
        "Host reachable",
        pi_ok,
        "Check SSH key and host address in ansible/inventory/hosts.ini"
        " — if the host key is unknown, run: make add-hostkey",
    )

    print()
    if all_ok:
        print("All checks passed — ready to run: make site")
    else:
        print("Fix the issues above before running make site.")
        sys.exit(1)


if __name__ == "__main__":
    main()
