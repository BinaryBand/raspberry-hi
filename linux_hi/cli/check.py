"""Validate prerequisites before running provisioning workflows."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from linux_hi.ansible.inventory import discover_hosts
from linux_hi.process.exec import resolve_executable, run_resolved
from linux_hi.vault.service import VAULT_PASSWORD_FILE, decrypt_vault
from models import ANSIBLE_DATA

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


def _check_python_version() -> bool:
    py_ok = sys.version_info >= MIN_PYTHON
    min_str = f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]}"
    run_str = f"{sys.version_info.major}.{sys.version_info.minor}"
    return check(
        f"Python >= {min_str} (running {run_str})",
        py_ok,
        f"pyenv install {min_str} && pyenv global {min_str}",
    )


def _check_ansible_available() -> bool:
    try:
        resolve_executable("ansible")
        found = True
    except FileNotFoundError:
        found = False
    return check("ansible available in PATH", found, "poetry install  (or: pipx install ansible)")


def _check_node_available() -> bool:
    try:
        resolve_executable("node")
        found = True
    except FileNotFoundError:
        found = False
    return check(
        "node available in PATH (for make cpd)",
        found,
        "install Node.js 18+ via nvm, your distro's package manager, or nodejs.org",
    )


def _check_vault_password_file() -> bool:
    vault_ok = VAULT_PASSWORD_FILE.exists() and VAULT_PASSWORD_FILE.stat().st_mode & 0o777 == 0o600
    return check(
        "Vault password file exists (ansible/.vault-password, mode 600)",
        vault_ok,
        "echo 'your-password' > ansible/.vault-password && chmod 600 ansible/.vault-password",
    )


def _check_host_reachable() -> bool:
    try:
        ping = run_resolved(
            ["ansible", "devices", "-m", "ping", "-i", str(ANSIBLE_DATA.inventory_file)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        pi_ok = ping.returncode == 0
    except Exception:
        pi_ok = False
    return check(
        "Host reachable",
        pi_ok,
        "Check SSH key and host address in ansible/inventory/hosts.yml"
        " — if the host key is unknown, run: make add-hostkey",
    )


def main(argv: Sequence[str] | None = None) -> None:
    """Run prerequisite checks and exit non-zero when any check fails."""
    args = parse_args(argv)

    if args.vault_only:
        if not check_vault_secrets():
            sys.exit(1)
        return

    print("Checking prerequisites...\n")
    all_ok = _check_python_version()
    all_ok &= _check_ansible_available()
    all_ok &= _check_node_available()
    vault_ok = _check_vault_password_file()
    all_ok &= vault_ok
    if vault_ok:
        all_ok &= check_vault_secrets()
    all_ok &= _check_host_reachable()

    print()
    if all_ok:
        print("All checks passed — ready to run: make site")
    else:
        print("Fix the issues above before running make site.")
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
