"""Vault access helpers."""

from .service import (
    VAULT_FILE,
    VAULT_PASSWORD_FILE,
    abort,
    decrypt_vault,
    decrypt_vault_raw,
    encrypt_vault,
    remove_become_password,
    remove_vault_key,
    setup_vault_password,
    write_become_password,
    write_vault_key,
)

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
