"""Presentation helpers for interactive storage workflows."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
	from models import BlockDevice

console = Console()

def display_devices(devices: list[BlockDevice]) -> None:
	"""Print *devices* as a Rich table."""
	table = Table(title="Available External Storage", header_style="bold cyan")
	table.add_column("#", style="dim", width=3)
	table.add_column("Device")
	table.add_column("Label")
	table.add_column("Size")
	table.add_column("Filesystem")
	table.add_column("Mount Point")

	for index, dev in enumerate(devices, start=1):
		table.add_row(
			str(index),
			f"/dev/{dev.name}",
			dev.label or "\u2014",
			dev.size or "\u2014",
			dev.fstype or "\u2014",
			dev.mountpoint or "not mounted",
		)

	console.print(table)

__all__ = ["display_devices"]
