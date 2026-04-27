"""Host inventory management commands."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from pathlib import Path

import questionary
from rich.console import Console
from rich.table import Table

from linux_hi.vault.service import remove_become_password, write_become_password
from models import ANSIBLE_DATA

_console = Console()


def cmd_list() -> None:
    """Print a table of configured inventory hosts and their connection details."""
    table = Table(show_header=True, header_style="bold")
    table.add_column("name")
    table.add_column("host")
    table.add_column("user")
    table.add_column("port")
    table.add_column("key")

    for alias in ANSIBLE_DATA.inventory_hosts():
        hv = ANSIBLE_DATA.host_vars(alias)
        key = Path(hv.ansible_ssh_private_key_file).name if hv.ansible_ssh_private_key_file else "—"
        table.add_row(
            alias,
            hv.ansible_host,
            hv.ansible_user or "—",
            str(hv.ansible_port or 22),
            key,
        )

    _console.print(table)


def cmd_add() -> None:
    """Interactively add a host to inventory, host_vars, and vault."""
    name = os.environ.get("NAME") or questionary.text("Host alias:").ask()
    addr = os.environ.get("ADDR") or questionary.text("Address (IP, mDNS, or hostname):").ask()
    user = os.environ.get("USER") or questionary.text("SSH user:", default="pi").ask()
    port_raw = os.environ.get("PORT") or questionary.text("SSH port:", default="22").ask()
    key = os.environ.get("KEY") or questionary.text("SSH private key path (blank to skip):").ask()
    password = questionary.password(f"Become (sudo) password for '{name}':").ask()

    if not all([name, addr, user, port_raw, password]):
        sys.exit("Aborted.")

    host_vars_data: dict[str, object] = {
        "ansible_host": addr,
        "ansible_user": user,
        "ansible_port": int(port_raw),
        "ansible_become_password": (
            "{{ (become_passwords | default({})).get(inventory_hostname, '') }}"
        ),
    }
    if key:
        host_vars_data["ansible_ssh_private_key_file"] = key

    try:
        ANSIBLE_DATA.add_inventory_host(name)
        ANSIBLE_DATA.write_host_vars_raw(name, host_vars_data)
        write_become_password(name, password)
    except Exception as e:
        sys.exit(f"  [FAIL]  {e}")

    print(f"  [OK  ]  Host '{name}' added to inventory, host_vars, and vault.")


def cmd_remove() -> None:
    """Interactively remove a host from inventory, host_vars, and vault."""
    hosts = ANSIBLE_DATA.inventory_hosts()
    if not hosts:
        sys.exit("No hosts configured.")

    name = (
        os.environ.get("NAME") or questionary.select("Select host to remove:", choices=hosts).ask()
    )

    if not name:
        sys.exit("Aborted.")
    if name not in hosts:
        sys.exit(f"  [FAIL]  Host '{name}' not found in inventory.")

    try:
        ANSIBLE_DATA.remove_inventory_host(name)
        ANSIBLE_DATA.remove_host_vars(name)
        remove_become_password(name)
    except Exception as e:
        sys.exit(f"  [FAIL]  {e}")

    print(f"  [OK  ]  Host '{name}' removed from inventory, host_vars, and vault.")


_SUBCOMMANDS: dict[str, Callable[[], None]] = {
    "add": cmd_add,
    "list": cmd_list,
    "remove": cmd_remove,
}


def main(argv: list[str] | None = None) -> None:
    """Dispatch host management subcommands."""
    args = argv if argv is not None else sys.argv[1:]
    subcmd = args[0] if args else "list"
    fn = _SUBCOMMANDS.get(subcmd)
    if fn is None:
        sys.exit(f"Unknown subcommand '{subcmd}'. Available: {', '.join(_SUBCOMMANDS)}")
    fn()


if __name__ == "__main__":
    main()
