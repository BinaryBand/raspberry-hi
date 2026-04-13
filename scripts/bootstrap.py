#!/usr/bin/env python3
"""
Interactive setup: create the vault password file and ensure all required
secrets are present in ansible/group_vars/all/vault.yml.

Safe to re-run — only prompts for credentials that are missing.

Run via: make bootstrap
"""

import getpass
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

# Ensure project root is on sys.path so local packages import correctly
# when the script is executed directly (e.g. `python scripts/bootstrap.py`).
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from models import VaultSecrets

ANSIBLE_DIR = Path(__file__).resolve().parent.parent / "ansible"
VAULT_PASSWORD_FILE = ANSIBLE_DIR / ".vault-password"
VAULT_FILE = ANSIBLE_DIR / "group_vars" / "all" / "vault.yml"

# Add new secrets here as the project grows.
SECRETS = [
    {"key": "minio_root_user", "label": "MinIO root username", "hidden": False},
    {"key": "minio_root_password", "label": "MinIO root password", "hidden": True},
]


def abort(msg: str) -> None:
    print(f"\nERROR: {msg}", file=sys.stderr)
    sys.exit(1)


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


def decrypt_vault() -> VaultSecrets:
    """Decrypt the vault file and return its contents as a VaultSecrets model."""
    result = subprocess.run(
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
    raw = yaml.safe_load(result.stdout) or {}
    return VaultSecrets.model_validate(raw)


def encrypt_vault(secrets: Any) -> None:
    """Write secrets (VaultSecrets or plain dict) to an encrypted vault file."""
    if hasattr(secrets, "model_dump"):
        data = secrets.model_dump()
    else:
        data = dict(secrets)

    plaintext = yaml.dump(data, default_flow_style=False)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False, dir=ANSIBLE_DIR) as tmp:
        tmp.write(plaintext)
        tmp_path = Path(tmp.name)

    try:
        result = subprocess.run(
            [
                "ansible-vault",
                "encrypt",
                str(tmp_path),
                "--vault-password-file",
                str(VAULT_PASSWORD_FILE),
                "--output",
                str(VAULT_FILE),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            abort(f"ansible-vault encrypt failed:\n{result.stderr.strip()}")
    finally:
        tmp_path.unlink(missing_ok=True)


def prompt_missing(secrets: VaultSecrets) -> dict:
    """Prompt for any secrets not already present. Returns only the new entries."""
    missing = [s for s in SECRETS if not getattr(secrets, s["key"], None)]
    if not missing:
        return {}

    print("Enter the following credentials (they will be encrypted in the vault):\n")
    new_entries = {}
    for s in missing:
        while True:
            value = (
                getpass.getpass(f"{s['label']}: ")
                if s["hidden"]
                else input(f"{s['label']}: ").strip()
            )
            if value:
                break
            print("  Value cannot be empty — try again.")
        new_entries[s["key"]] = value
    return new_entries


def main() -> None:
    print("=== raspberry-hi bootstrap ===\n")

    setup_vault_password()

    existing = decrypt_vault() if VAULT_FILE.exists() else VaultSecrets()
    new_entries = prompt_missing(existing)

    if not new_entries:
        print("All secrets are present — nothing to do.")
        print("To update a value, run: make vault-edit")
        return

    updated = {**existing.model_dump(), **new_entries}
    encrypt_vault(updated)

    added = ", ".join(new_entries)
    print(f"\nVault updated ({added}).")
    print("Run 'make check' then 'make site' to provision.\n")


if __name__ == "__main__":
    main()
