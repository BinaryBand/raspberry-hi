"""Interactive bootstrap flow for vault password and become secrets."""

from __future__ import annotations

import getpass

from models import VaultSecrets
from scripts.utils.inventory_service import discover_hosts
from scripts.utils.vault_service import (
    VAULT_FILE,
    decrypt_vault_raw,
    encrypt_vault,
    setup_vault_password,
)


def prompt_missing_become_passwords(existing: dict[str, str], hosts: list[str]) -> dict[str, str]:
    """Prompt for become passwords for any hosts not yet in the vault dict."""
    missing = [host for host in hosts if not existing.get(host)]
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
    """Run interactive first-time secret bootstrap."""
    print("=== linux-hi bootstrap ===\n")

    setup_vault_password()

    if VAULT_FILE.exists():
        raw = decrypt_vault_raw()
        existing = VaultSecrets.model_validate(raw)
    else:
        existing = VaultSecrets()
        raw = {}

    hosts = discover_hosts()
    current_become = dict(existing.become_passwords or {})
    new_become = prompt_missing_become_passwords(current_become, hosts)

    if not new_become:
        print("All secrets are present — nothing to do.")
        print("To update a value, run: make vault-edit")
        return

    updated_become = {**current_become, **new_become}
    updated = {**raw, "become_passwords": updated_become}
    encrypt_vault(updated)

    added_keys = [f"become_passwords.{host}" for host in new_become]
    print(f"\nVault updated ({', '.join(added_keys)}).")
    print("Run 'make check' then 'make minio' (or other app targets) to provision.\n")
