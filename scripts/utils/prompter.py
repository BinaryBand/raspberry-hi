"""Prompting port implementations used by interactive setup scripts.

Defines a small `Prompter` protocol and a `QuestionaryPrompter` that
delegates to `questionary` + `rich` for display. Kept intentionally small
so tests can stub the protocol.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import questionary
from rich.console import Console

if TYPE_CHECKING:
    from models import BlockDevice

console = Console()


class Prompter(Protocol):
    def choose_device(self, devices: list["BlockDevice"]) -> "BlockDevice | None": ...

    def ask_label(self, default: str | None) -> str | None: ...


class QuestionaryPrompter:
    """Prompter implementation backed by `questionary`.

    This mirrors the behaviour previously inline in the old flow helpers.
    """

    def choose_device(self, devices: list["BlockDevice"]) -> "BlockDevice | None":
        from .storage_utils import display_devices

        if not devices:
            return None

        display_devices(devices)

        choices = [
            questionary.Choice(
                title=f"/dev/{d.name}  {d.label or ''}  ({d.size or '?'})",
                value=d,
            )
            for d in devices
        ]

        selected = questionary.select("Select a device to mount:", choices=choices).ask()
        return selected

    def ask_label(self, default: str | None) -> str | None:
        return questionary.text(
            "Mount point label (will mount at /mnt/<label>):",
            default=default or "",
        ).ask()
