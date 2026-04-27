"""Vault access helpers."""

from __future__ import annotations

import getpass
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

from linux_hi.ansible.yaml import yaml_mapping
from linux_hi.process.exec import run_resolved
from models import ANSIBLE_DATA, VaultSecrets

VAULT_PASSWORD_FILE = ANSIBLE_DATA.ansible_dir / ".vault-password"
VAULT_FILE = ANSIBLE_DATA.ansible_dir / "group_vars" / "all" / "vault.yml"

RawVaultData = dict[str, Any]


def abort(message: str) -> None:
    """Print an error and terminate the current script flow."""
    print(f"\nERROR: {message}", file=sys.stderr)
    sys.exit(1)


def setup_vault_password(vault_password_file: Path = VAULT_PASSWORD_FILE) -> None:
    """Create the local vault password file if it does not already exist."""
    if vault_password_file.exists():
        return

    print("No vault password file found. Let's create one.")
    while True:
        password = getpass.getpass("Choose a vault password: ")
        confirm = getpass.getpass("Confirm vault password: ")
        if password == confirm:
            break
        print("Passwords do not match — try again.")

    vault_password_file.write_text(password)
    vault_password_file.chmod(0o600)
    print(f"Vault password saved to {vault_password_file}\n")


def decrypt_vault_raw(
    vault_file: Path = VAULT_FILE,
    vault_password_file: Path = VAULT_PASSWORD_FILE,
) -> RawVaultData:
    """Decrypt the vault file and return its raw contents as a dict."""
    result = run_resolved(
        [
            "ansible-vault",
            "decrypt",
            str(vault_file),
            "--vault-password-file",
            str(vault_password_file),
            "--output",
            "-",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        abort(f"Could not decrypt vault:\n{result.stderr.strip()}")
    return yaml_mapping(yaml.safe_load(result.stdout), source=vault_file)


def decrypt_vault(
    vault_file: Path = VAULT_FILE,
    vault_password_file: Path = VAULT_PASSWORD_FILE,
) -> VaultSecrets:
    """Decrypt the vault file and validate it as VaultSecrets."""
    return VaultSecrets.model_validate(decrypt_vault_raw(vault_file, vault_password_file))


def encrypt_vault(
    data: RawVaultData,
    output: Path | None = None,
    *,
    vault_file: Path = VAULT_FILE,
) -> None:
    """Encrypt and write the vault file from a dict."""
    with tempfile.NamedTemporaryFile("w", delete=False) as tmp:
        yaml.safe_dump(data, tmp)
        tmp.flush()
        result = run_resolved(
            [
                "ansible-vault",
                "encrypt",
                tmp.name,
                "--vault-password-file",
                str(VAULT_PASSWORD_FILE),
                "--output",
                str(output or vault_file),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            abort(f"Could not encrypt vault:\n{result.stderr.strip()}")


def write_vault_key(key: str, value: str) -> None:
    """Add or update an arbitrary top-level key in the vault."""
    data = decrypt_vault_raw()
    data[key] = value
    encrypt_vault(data)


def remove_vault_key(key: str) -> None:
    """Remove a top-level key from the vault, silently ignoring missing keys."""
    data = decrypt_vault_raw()
    data.pop(key, None)
    encrypt_vault(data)


def write_become_password(hostname: str, password: str) -> None:
    """Add or update the become password for a host in the vault."""
    data = decrypt_vault_raw()
    become: dict[str, Any] = dict(data.get("become_passwords") or {})
    become[hostname] = password
    data["become_passwords"] = become
    encrypt_vault(data)


def remove_become_password(hostname: str) -> None:
    """Remove the become password for a host from the vault."""
    data = decrypt_vault_raw()
    become: dict[str, Any] = dict(data.get("become_passwords") or {})
    become.pop(hostname, None)
    data["become_passwords"] = become
    encrypt_vault(data)


__all__ = [
    "VAULT_FILE",
    "VAULT_PASSWORD_FILE",
    "abort",
    "decrypt_vault",
    "decrypt_vault_raw",
    "encrypt_vault",
    "remove_become_password",
    "remove_vault_key",
    "setup_vault_password",
    "write_become_password",
    "write_vault_key",
]
