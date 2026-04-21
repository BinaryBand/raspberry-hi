"""Validate prerequisites before running provisioning workflows."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from models import ANSIBLE_DATA
from scripts.utils.exec_utils import resolve_executable, run_resolved
from scripts.utils.inventory_service import discover_hosts
from scripts.utils.vault_service import VAULT_PASSWORD_FILE, decrypt_vault

MIN_PYTHON = (3, 12)


def check(label: str, ok: bool, fix: str = "") -> bool:
    """Print a check result and return the same boolean status."""
    mark = "OK  " if ok else "FAIL"
    print(f"  [{mark}]  {label}")
    if not ok and fix:
        print(f"          fix: {fix}")
    return ok


def check_vault_secrets() -> bool:
    """Verify the vault is decryptable and become passwords are set for all hosts."""
    if not VAULT_PASSWORD_FILE.exists():
        return check(
            "Vault secrets complete",
            False,
            "run `make bootstrap` — vault password file is missing",
        )

    secrets = decrypt_vault()
    hosts = discover_hosts()
    become_pwds = secrets.become_passwords or {}
    missing_hosts = [host for host in hosts if not become_pwds.get(host)]

    return check(
        "Vault secrets complete",
        not missing_hosts,
        "run `make bootstrap` to add: "
        + ", ".join(f"become_passwords.{host}" for host in missing_hosts)
        if missing_hosts
        else "",
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for prerequisite checks."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--vault-only",
        action="store_true",
        help="Run only the vault/password validation check.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """Run prerequisite checks and exit non-zero when any check fails."""
    args = parse_args(argv)

    if args.vault_only:
        all_ok = check_vault_secrets()
        if not all_ok:
            sys.exit(1)
        return

    print("Checking prerequisites...\n")
    all_ok = True

    py_ok = sys.version_info >= MIN_PYTHON
    min_str = f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]}"
    run_str = f"{sys.version_info.major}.{sys.version_info.minor}"
    all_ok &= check(
        f"Python >= {min_str} (running {run_str})",
        py_ok,
        f"pyenv install {min_str} && pyenv global {min_str}",
    )

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

    vault_ok = VAULT_PASSWORD_FILE.exists() and VAULT_PASSWORD_FILE.stat().st_mode & 0o777 == 0o600
    all_ok &= check(
        "Vault password file exists (ansible/.vault-password, mode 600)",
        vault_ok,
        "echo 'your-password' > ansible/.vault-password && chmod 600 ansible/.vault-password",
    )

    if vault_ok:
        all_ok &= check_vault_secrets()

    inventory_path = ANSIBLE_DATA.inventory_file
    try:
        ping = run_resolved(
            ["ansible", "devices", "-m", "ping", "-i", str(inventory_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        pi_ok = ping.returncode == 0
    except Exception:
        pi_ok = False
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
    main(sys.argv[1:])
