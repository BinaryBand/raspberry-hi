"""Host inventory management commands."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import questionary
from rich.console import Console
from rich.table import Table

from linux_hi.vault.service import remove_become_password, write_become_password
from models import ANSIBLE_DATA

_console = Console()


def _pick(*values: str | None) -> str | None:
    """Return the first non-empty string in *values* or None."""
    for value in values:
        if value:
            return value
    return None


def _prompt_if_missing(value: str | None, label: str, default: str | None = None) -> str | None:
    """Prompt with *label* when *value* is missing, preserving an optional default."""
    if value:
        return value
    return questionary.text(label, default=default or "").ask()


def _resolve_port(value: int | None) -> int:
    """Resolve CLI/env/prompt port input into an integer or terminate on invalid input."""
    if value is not None:
        return value
    port_raw = os.environ.get("PORT") or questionary.text("SSH port:", default="22").ask()
    if not port_raw:
        sys.exit("Aborted.")
    try:
        return int(port_raw)
    except ValueError:
        sys.exit("  [FAIL]  PORT must be an integer.")


def cmd_list(args: argparse.Namespace) -> None:
    """Print a table of configured inventory hosts and their connection details."""
    table = Table(show_header=True, header_style="bold")
    for col in ("name", "host", "user", "port", "key"):
        table.add_column(col)
    for alias in ANSIBLE_DATA.inventory_hosts():
        hv = ANSIBLE_DATA.host_vars(alias)
        key = Path(hv.ansible_ssh_private_key_file).name if hv.ansible_ssh_private_key_file else "—"
        table.add_row(
            alias, hv.ansible_host, hv.ansible_user or "—", str(hv.ansible_port or 22), key
        )
    _console.print(table)


def cmd_add(args: argparse.Namespace) -> None:
    """Interactively add a host to inventory, host_vars, and vault."""
    from typing import cast

    name = _prompt_if_missing(_pick(args.name, os.environ.get("NAME")), "Host alias:")
    addr = _prompt_if_missing(
        _pick(args.address, os.environ.get("ADDRESS"), os.environ.get("ADDR")),
        "Address (IP, mDNS, or hostname):",
    )
    user = _prompt_if_missing(_pick(args.user, os.environ.get("USER")), "SSH user:", default="pi")
    port = _resolve_port(args.port)
    secret = _pick(args.secret, os.environ.get("SECRET"), os.environ.get("KEY"))
    if secret is None:
        secret = questionary.text("SSH private key path (blank to skip):").ask()
    password = questionary.password(f"Become (sudo) password for '{name}':").ask()

    if not all([name, addr, user, password]):
        sys.exit("Aborted.")

    host_vars_data: dict[str, object] = {
        "ansible_host": addr,
        "ansible_user": user,
        "ansible_port": port,
        "ansible_become_password": (
            "{{ (become_passwords | default({})).get(inventory_hostname, '') }}"
        ),
    }
    if secret:
        host_vars_data["ansible_ssh_private_key_file"] = secret

    try:
        ANSIBLE_DATA.add_inventory_host(cast(str, name))
        ANSIBLE_DATA.write_host_vars_raw(cast(str, name), host_vars_data)
        write_become_password(cast(str, name), cast(str, password))
    except Exception as exc:
        sys.exit(f"  [FAIL]  {exc}")

    print(f"  [OK  ]  Host '{name}' added to inventory, host_vars, and vault.")


def cmd_remove(args: argparse.Namespace) -> None:
    """Interactively remove a host from inventory, host_vars, and vault."""
    hosts = ANSIBLE_DATA.inventory_hosts()
    if not hosts:
        sys.exit("No hosts configured.")

    name = args.name or os.environ.get("NAME")
    if not name:
        name = questionary.select("Select host to remove:", choices=hosts).ask()
    if not name:
        sys.exit("Aborted.")
    if name not in hosts:
        sys.exit(f"  [FAIL]  Host '{name}' not found in inventory.")

    try:
        ANSIBLE_DATA.remove_inventory_host(name)
        ANSIBLE_DATA.remove_host_vars(name)
        remove_become_password(name)
    except Exception as exc:
        sys.exit(f"  [FAIL]  {exc}")

    print(f"  [OK  ]  Host '{name}' removed from inventory, host_vars, and vault.")


def main(argv: list[str] | None = None) -> None:
    """Dispatch host management subcommands."""
    parser = argparse.ArgumentParser(description="Host inventory management")
    parser.set_defaults(func=cmd_list)
    sub = parser.add_subparsers()

    list_p = sub.add_parser("list", help="List configured hosts")
    list_p.set_defaults(func=cmd_list)

    add_p = sub.add_parser("add", help="Add a host to inventory")
    add_p.add_argument("--name")
    add_p.add_argument("--address")
    add_p.add_argument("--secret")
    add_p.add_argument("--user")
    add_p.add_argument("--port", type=int)
    add_p.set_defaults(func=cmd_add)

    rm_p = sub.add_parser("remove", help="Remove a host from inventory")
    rm_p.add_argument("--name")
    rm_p.set_defaults(func=cmd_remove)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
