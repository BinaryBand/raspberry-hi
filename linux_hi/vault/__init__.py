"""Vault access helpers."""

from .service import (
    VAULT_FILE,
    VAULT_PASSWORD_FILE,
    abort,
    decrypt_vault,
    decrypt_vault_raw,
    encrypt_vault,
    setup_vault_password,
)

__all__ = [
    "VAULT_FILE",
    "VAULT_PASSWORD_FILE",
    "abort",
    "decrypt_vault",
    "decrypt_vault_raw",
    "encrypt_vault",
    "setup_vault_password",
]
