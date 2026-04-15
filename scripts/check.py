#!/usr/bin/env python3
"""Validate prerequisites before running make site."""

import sys

from utils.ansible_utils import ANSIBLE_DIR
from utils.exec_utils import run_resolved

VAULT_PASSWORD_FILE = ANSIBLE_DIR / ".vault-password"


def check(label: str, ok: bool, fix: str = "") -> bool:
    mark = "OK  " if ok else "FAIL"
    print(f"  [{mark}]  {label}")
    if not ok and fix:
        print(f"          fix: {fix}")
    return ok


def main() -> None:
    print("Checking prerequisites...\n")
    all_ok = True

    # Vault password file exists and is private
    vault_ok = VAULT_PASSWORD_FILE.exists() and VAULT_PASSWORD_FILE.stat().st_mode & 0o777 == 0o600
    all_ok &= check(
        "Vault password file exists (ansible/.vault-password, mode 600)",
        vault_ok,
        "echo 'your-password' > ansible/.vault-password && chmod 600 ansible/.vault-password",
    )

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
