"""Vault key management commands."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable

import questionary
from rich.console import Console
from rich.table import Table

from linux_hi.cli._dispatch import dispatch
from linux_hi.vault.service import decrypt_vault_raw, remove_vault_key, write_vault_key

_console = Console()


def cmd_list() -> None:
    """Print a table of top-level vault keys (no values shown)."""
    data = decrypt_vault_raw()
    table = Table(show_header=True, header_style="bold")
    table.add_column("key")
    table.add_column("type")
    for key, value in data.items():
        table.add_row(key, type(value).__name__)
    _console.print(table)


def cmd_add() -> None:
    """Add or update a top-level key in the vault."""
    key = os.environ.get("NAME") or questionary.text("Vault key:").ask()
    if not key:
        sys.exit("Aborted.")
    value = questionary.password(f"Value for '{key}':").ask()
    if value is None:
        sys.exit("Aborted.")

    try:
        write_vault_key(key, value)
    except Exception as e:
        sys.exit(f"  [FAIL]  {e}")

    print(f"  [OK  ]  Vault key '{key}' written.")


def cmd_remove() -> None:
    """Remove a top-level key from the vault."""
    data = decrypt_vault_raw()
    keys = list(data.keys())
    if not keys:
        sys.exit("Vault is empty.")

    key = os.environ.get("NAME") or questionary.select("Select key to remove:", choices=keys).ask()
    if not key:
        sys.exit("Aborted.")

    try:
        remove_vault_key(key)
    except Exception as e:
        sys.exit(f"  [FAIL]  {e}")

    print(f"  [OK  ]  Vault key '{key}' removed.")


_SUBCOMMANDS: dict[str, Callable[[], None]] = {
    "add": cmd_add,
    "list": cmd_list,
    "remove": cmd_remove,
}


def main(argv: list[str] | None = None) -> None:
    """Dispatch vault key management subcommands."""
    dispatch(_SUBCOMMANDS, argv)


if __name__ == "__main__":
    main()
