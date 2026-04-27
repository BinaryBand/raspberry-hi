"""Host inventory management commands."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import TypeAlias, cast

import questionary
from rich.console import Console
from rich.table import Table

from linux_hi.orchestration.config import HostsConfigController
from linux_hi.vault.service import remove_become_password, write_become_password
from models import ANSIBLE_DATA

_console = Console()
HostRow: TypeAlias = dict[str, str]
HostRows: TypeAlias = list[HostRow]


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


class _HostsAdapter:
    """Adapter implementing host add/remove/list against repository stores."""

    def list(self) -> HostRows:
        rows: HostRows = []
        for alias in ANSIBLE_DATA.inventory_hosts():
            hv = ANSIBLE_DATA.host_vars(alias)
            key = (
                Path(hv.ansible_ssh_private_key_file).name
                if hv.ansible_ssh_private_key_file
                else "—"
            )
            rows.append(
                {
                    "name": alias,
                    "host": hv.ansible_host,
                    "user": hv.ansible_user or "—",
                    "port": str(hv.ansible_port or 22),
                    "key": key,
                }
            )
        return rows

    def add(
        self,
        *,
        name: str,
        address: str,
        user: str | None,
        port: int | None,
        secret: str | None,
        password: str,
    ) -> None:
        host_vars_data: dict[str, object] = {
            "ansible_host": address,
            "ansible_user": user,
            "ansible_port": port,
            "ansible_become_password": (
                "{{ (become_passwords | default({})).get(inventory_hostname, '') }}"
            ),
        }
        if secret:
            host_vars_data["ansible_ssh_private_key_file"] = secret

        ANSIBLE_DATA.add_inventory_host(name)
        ANSIBLE_DATA.write_host_vars_raw(name, host_vars_data)
        write_become_password(name, password)

    def remove(self, *, name: str) -> None:
        ANSIBLE_DATA.remove_inventory_host(name)
        ANSIBLE_DATA.remove_host_vars(name)
        remove_become_password(name)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    sub = parser.add_subparsers(dest="subcmd")

    add_p = sub.add_parser("add", add_help=False)
    add_p.add_argument("--name")
    add_p.add_argument("--address")
    add_p.add_argument("--secret")
    add_p.add_argument("--user")
    add_p.add_argument("--port", type=int)

    rm_p = sub.add_parser("remove", add_help=False)
    rm_p.add_argument("--name")

    sub.add_parser("list", add_help=False)
    return parser


def cmd_list() -> None:
    """Print a table of configured inventory hosts and their connection details."""
    controller = HostsConfigController(_HostsAdapter())
    rows = controller.list()

    table = Table(show_header=True, header_style="bold")
    table.add_column("name")
    table.add_column("host")
    table.add_column("user")
    table.add_column("port")
    table.add_column("key")

    for row in rows:
        table.add_row(row["name"], row["host"], row["user"], row["port"], row["key"])

    _console.print(table)


def cmd_add(args: argparse.Namespace) -> None:
    """Interactively add a host to inventory, host_vars, and vault."""
    name = _prompt_if_missing(
        _pick(args.name, os.environ.get("NAME")),
        "Host alias:",
    )
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

    name = cast(str, name)
    addr = cast(str, addr)
    user = cast(str, user)
    password = cast(str, password)

    controller = HostsConfigController(_HostsAdapter())
    try:
        controller.add(
            name=name,
            address=addr,
            user=user,
            port=port,
            secret=secret or None,
            password=password,
        )
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

    controller = HostsConfigController(_HostsAdapter())
    try:
        controller.remove(name=name)
    except Exception as exc:
        sys.exit(f"  [FAIL]  {exc}")

    print(f"  [OK  ]  Host '{name}' removed from inventory, host_vars, and vault.")


def main(argv: list[str] | None = None) -> None:
    """Dispatch host management subcommands."""
    args_list = argv if argv is not None else sys.argv[1:]
    parser = _build_parser()
    parsed, _ = parser.parse_known_args(args_list)
    subcmd = parsed.subcmd or "list"

    if subcmd == "list":
        cmd_list()
        return
    if subcmd == "add":
        cmd_add(parsed)
        return
    if subcmd == "remove":
        cmd_remove(parsed)
        return

    sys.exit("Unknown subcommand. Available: add, list, remove")


if __name__ == "__main__":
    main()
