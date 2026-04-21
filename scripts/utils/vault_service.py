from __future__ import annotations

import getpass
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

from linux_hi.process.exec import run_resolved
from linux_hi.vault.service import *
from models import ANSIBLE_DATA, VaultSecrets
from scripts.utils.yaml_utils import yaml_mapping

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
    vault_password_file: Path = VAULT_PASSWORD_FILE,
) -> None:
    """Write *data* to an encrypted vault file."""
    target = output or vault_file
    plaintext = yaml.dump(data, default_flow_style=False)

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yml",
        delete=False,
        dir=ANSIBLE_DATA.ansible_dir,
    ) as tmp:
        tmp.write(plaintext)
        tmp_path = Path(tmp.name)

    try:
        result = run_resolved(
            [
                "ansible-vault",
                "encrypt",
                str(tmp_path),
                "--vault-password-file",
                str(vault_password_file),
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


def replace_vault_data(secret_updates: RawVaultData, vault_file: Path = VAULT_FILE) -> int:
    """Merge *secret_updates* into the vault and replace the encrypted file atomically."""
    raw = decrypt_vault_raw(vault_file)
    raw.update(secret_updates)
    tmp = vault_file.with_suffix(".tmp")
    encrypt_vault(raw, output=tmp, vault_file=vault_file)
    tmp.replace(vault_file)
    return len(secret_updates)
