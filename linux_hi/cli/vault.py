"""Vault key management commands."""

from __future__ import annotations

import argparse
import os
import sys

import questionary
from rich.console import Console
from rich.table import Table

from linux_hi.vault.service import decrypt_vault_raw, remove_vault_key, write_vault_key

_console = Console()


def cmd_list(args: argparse.Namespace) -> None:
    """Print a table of top-level vault keys (no values shown)."""
    table = Table(show_header=True, header_style="bold")
    table.add_column("key")
    table.add_column("type")
    for key, value in decrypt_vault_raw().items():
        table.add_row(key, type(value).__name__)
    _console.print(table)


def cmd_add(args: argparse.Namespace) -> None:
    """Add or update a top-level key in the vault."""
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


def cmd_remove(args: argparse.Namespace) -> None:
    """Remove a top-level key from the vault."""
    keys = list(decrypt_vault_raw())
    if not keys:
        sys.exit("Vault is empty.")

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


def main(argv: list[str] | None = None) -> None:
    """Dispatch vault key management subcommands."""
    parser = argparse.ArgumentParser(description="Vault key management")
    parser.set_defaults(func=cmd_list)
    sub = parser.add_subparsers()

    list_p = sub.add_parser("list", help="List vault keys")
    list_p.set_defaults(func=cmd_list)

    add_p = sub.add_parser("add", help="Add or update a vault key")
    add_p.add_argument("--name")
    add_p.set_defaults(func=cmd_add)

    rm_p = sub.add_parser("remove", help="Remove a vault key")
    rm_p.add_argument("--name")
    rm_p.set_defaults(func=cmd_remove)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
