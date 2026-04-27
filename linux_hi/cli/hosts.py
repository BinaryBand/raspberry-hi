"""Host inventory management commands."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

from rich.console import Console
from rich.table import Table

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


_SUBCOMMANDS: dict[str, Callable[[], None]] = {
    "list": cmd_list,
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
