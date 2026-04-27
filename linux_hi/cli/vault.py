"""Vault key management commands."""

from __future__ import annotations

import argparse
import os
import sys
from typing import TypeAlias

import questionary
from rich.console import Console
from rich.table import Table

from linux_hi.orchestration.config import VaultConfigController
from linux_hi.vault.service import decrypt_vault_raw, remove_vault_key, write_vault_key

_console = Console()
VaultRows: TypeAlias = list[tuple[str, str]]


class _VaultAdapter:
    """Adapter implementing vault add/remove/list against encrypted store."""

    def list(self) -> VaultRows:
        data = decrypt_vault_raw()
        return [(key, type(value).__name__) for key, value in data.items()]

    def add(self, *, name: str, value: str) -> None:
        write_vault_key(name, value)

    def remove(self, *, name: str) -> None:
        remove_vault_key(name)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("subcmd", nargs="?", default="list", choices=("add", "list", "remove"))
    parser.add_argument("--name")
    return parser


def cmd_list() -> None:
    """Print a table of top-level vault keys (no values shown)."""
    controller = VaultConfigController(_VaultAdapter())
    rows = controller.list()

    table = Table(show_header=True, header_style="bold")
    table.add_column("key")
    table.add_column("type")
    for key, value_type in rows:
        table.add_row(key, value_type)
    _console.print(table)


def cmd_add(args: argparse.Namespace) -> None:
    """Add or update a top-level key in the vault."""
    key = args.name or os.environ.get("NAME") or questionary.text("Vault key:").ask()
    if not key:
        sys.exit("Aborted.")
    value = questionary.password(f"Value for '{key}':").ask()
    if value is None:
        sys.exit("Aborted.")

    controller = VaultConfigController(_VaultAdapter())
    try:
        controller.add(name=key, value=value)
    except Exception as exc:
        sys.exit(f"  [FAIL]  {exc}")

    print(f"  [OK  ]  Vault key '{key}' written.")


def cmd_remove(args: argparse.Namespace) -> None:
    """Remove a top-level key from the vault."""
    rows = VaultConfigController(_VaultAdapter()).list()
    keys = [key for key, _ in rows]
    if not keys:
        sys.exit("Vault is empty.")

    key = args.name or os.environ.get("NAME")
    if not key:
        key = questionary.select("Select key to remove:", choices=keys).ask()
    if not key:
        sys.exit("Aborted.")

    controller = VaultConfigController(_VaultAdapter())
    try:
        controller.remove(name=key)
    except Exception as exc:
        sys.exit(f"  [FAIL]  {exc}")

    print(f"  [OK  ]  Vault key '{key}' removed.")


def main(argv: list[str] | None = None) -> None:
    """Dispatch vault key management subcommands."""
    args_list = argv if argv is not None else sys.argv[1:]
    parser = _build_parser()
    parsed, _ = parser.parse_known_args(args_list)
    subcmd = parsed.subcmd

    if subcmd == "list":
        cmd_list()
    elif subcmd == "add":
        cmd_add(parsed)
    elif subcmd == "remove":
        cmd_remove(parsed)
    else:
        sys.exit("Unknown subcommand. Available: add, list, remove")


if __name__ == "__main__":
    main()
