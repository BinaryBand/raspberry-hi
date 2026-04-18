#!/usr/bin/env python3
"""
Interactive setup: create the vault password file and ensure all required
secrets are present in ansible/group_vars/all/vault.yml.

Safe to re-run — only prompts for credentials that are missing.
Adding a new host to hosts.ini and re-running will prompt only for that
host's become password; nothing else changes.

Run via: make bootstrap
"""

from __future__ import annotations

import configparser
import getpass
import sys
import tempfile
from pathlib import Path
from typing import Any, TypedDict

import yaml
from utils.ansible_utils import ANSIBLE_DIR
from utils.exec_utils import run_resolved
from utils.yaml_utils import yaml_mapping

from models import VaultSecrets

VAULT_PASSWORD_FILE = ANSIBLE_DIR / ".vault-password"
VAULT_FILE = ANSIBLE_DIR / "group_vars" / "all" / "vault.yml"
INVENTORY_FILE = ANSIBLE_DIR / "inventory" / "hosts.ini"


class SecretSpec(TypedDict):
    key: str
    label: str
    hidden: bool


RawVaultData = dict[str, Any]


def abort(msg: str) -> None:
    print(f"\nERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def discover_hosts() -> list[str]:
    """Return all hostnames from the Ansible inventory without requiring Ansible."""
    parser = configparser.ConfigParser(allow_no_value=True)
    parser.read(INVENTORY_FILE)
    seen: set[str] = set()
    hosts: list[str] = []
    for section in parser.sections():
        for host in parser.options(section):
            if host not in seen:
                seen.add(host)
                hosts.append(host)
    return hosts


def setup_vault_password() -> None:
    if VAULT_PASSWORD_FILE.exists():
        return

    print("No vault password file found. Let's create one.")
    while True:
        pw = getpass.getpass("Choose a vault password: ")
        confirm = getpass.getpass("Confirm vault password: ")
        if pw == confirm:
            break
        print("Passwords do not match — try again.")

    VAULT_PASSWORD_FILE.write_text(pw)
    VAULT_PASSWORD_FILE.chmod(0o600)
    print(f"Vault password saved to {VAULT_PASSWORD_FILE}\n")


def decrypt_vault_raw() -> RawVaultData:
    """Decrypt the vault file and return its raw contents as a dict."""
    result = run_resolved(
        [
            "ansible-vault",
            "decrypt",
            str(VAULT_FILE),
            "--vault-password-file",
            str(VAULT_PASSWORD_FILE),
            "--output",
            "-",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        abort(f"Could not decrypt vault:\n{result.stderr.strip()}")
    return yaml_mapping(yaml.safe_load(result.stdout), source=VAULT_FILE)


def decrypt_vault() -> VaultSecrets:
    """Decrypt the vault file and return its contents as a VaultSecrets model."""
    return VaultSecrets.model_validate(decrypt_vault_raw())


def encrypt_vault(data: RawVaultData, output: Path | None = None) -> None:
    """Write *data* to an encrypted vault file.

    *output* defaults to VAULT_FILE. Pass an alternate path to write to a
    temporary location first (for atomic replace patterns).
    """
    target = output or VAULT_FILE
    plaintext = yaml.dump(data, default_flow_style=False)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False, dir=ANSIBLE_DIR) as tmp:
        tmp.write(plaintext)
        tmp_path = Path(tmp.name)

    try:
        result = run_resolved(
            [
                "ansible-vault",
                "encrypt",
                str(tmp_path),
                "--vault-password-file",
                str(VAULT_PASSWORD_FILE),
                "--output",
                str(target),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            abort(f"ansible-vault encrypt failed:\n{result.stderr.strip()}")
    finally:
        tmp_path.unlink(missing_ok=True)


def prompt_missing_become_passwords(existing: dict[str, str], hosts: list[str]) -> dict[str, str]:
    """Prompt for become passwords for any hosts not yet in the vault dict."""
    missing = [h for h in hosts if not existing.get(h)]
    if not missing:
        return {}

    print("Enter sudo (become) passwords for the following hosts:\n")
    new_entries: dict[str, str] = {}
    for host in missing:
        while True:
            value = getpass.getpass(f"  {host} sudo password: ")
            if value:
                break
            print("  Value cannot be empty — try again.")
        new_entries[host] = value
    return new_entries


def main() -> None:
    print("=== raspberry-hi bootstrap ===\n")

    setup_vault_password()

    if VAULT_FILE.exists():
        raw = decrypt_vault_raw()
        existing = VaultSecrets.model_validate(raw)
    else:
        existing = VaultSecrets()
        raw = {}

    # Prompt for missing per-host become passwords.
    hosts = discover_hosts()
    current_become = dict(existing.become_passwords or {})
    new_become = prompt_missing_become_passwords(current_become, hosts)

    if not new_become:
        print("All secrets are present — nothing to do.")
        print("To update a value, run: make vault-edit")
        return

    # Merge and save.
    updated_become = {**current_become, **new_become}
    updated = {**raw, "become_passwords": updated_become}
    encrypt_vault(updated)

    added_keys = [f"become_passwords.{h}" for h in new_become]
    print(f"\nVault updated ({', '.join(added_keys)}).")
    print("Run 'make check' then 'make minio' (or other app targets) to provision.\n")


if __name__ == "__main__":
    main()
