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

import getpass

from utils.inventory_service import discover_hosts
from utils.vault_service import (
    VAULT_FILE,
    decrypt_vault_raw,
    encrypt_vault,
    setup_vault_password,
)

from models import VaultSecrets


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
    print("=== linux-hi bootstrap ===\n")

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
