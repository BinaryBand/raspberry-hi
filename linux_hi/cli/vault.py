"""Vault key management commands."""

from __future__ import annotations

import argparse
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
    table = Table(show_header=True, header_style="bold")
    table.add_column("key")
    table.add_column("type")
    for key, value in decrypt_vault_raw().items():
        table.add_row(key, type(value).__name__)
    _console.print(table)


def cmd_add() -> None:
    """Add or update a top-level key in the vault."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--name")
    args, _ = parser.parse_known_args()

    key = args.name or os.environ.get("NAME") or questionary.text("Vault key:").ask()
    if not key:
        sys.exit("Aborted.")
    value = questionary.password(f"Value for '{key}':").ask()
    if value is None:
        sys.exit("Aborted.")

    try:
        write_vault_key(key, value)
    except Exception as exc:
        sys.exit(f"  [FAIL]  {exc}")

    print(f"  [OK  ]  Vault key '{key}' written.")


def cmd_remove() -> None:
    """Remove a top-level key from the vault."""
    keys = list(decrypt_vault_raw())
    if not keys:
        sys.exit("Vault is empty.")

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--name")
    args, _ = parser.parse_known_args()

    key = args.name or os.environ.get("NAME")
    if not key:
        key = questionary.select("Select key to remove:", choices=keys).ask()
    if not key:
        sys.exit("Aborted.")

    try:
        remove_vault_key(key)
    except Exception as exc:
        sys.exit(f"  [FAIL]  {exc}")

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
