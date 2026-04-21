"""Prompting port implementations used by interactive setup scripts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import questionary

if TYPE_CHECKING:
    from models import BlockDevice


class Prompter(Protocol):
    """Port for interactive mount prompts."""

    def choose_device(self, devices: list["BlockDevice"]) -> "BlockDevice | None":
        """Return the selected device or None when the user aborts."""
        ...

    def ask_label(self, default: str | None) -> str | None:
        """Return the mount label or None when the user aborts."""
        ...


class QuestionaryPrompter:
    """Prompter implementation backed by questionary."""

    def choose_device(self, devices: list["BlockDevice"]) -> "BlockDevice | None":
        """Prompt for a device choice after displaying candidates."""
        from linux_hi.storage.display import display_devices

        if not devices:
            return None

        display_devices(devices)

        choices = [
            questionary.Choice(
                title=f"/dev/{device.name}  {device.label or ''}  ({device.size or '?'})",
                value=device,
            )
            for device in devices
        ]

        return questionary.select("Select a device to mount:", choices=choices).ask()

    def ask_label(self, default: str | None) -> str | None:
        """Prompt for a mount label, seeding with the suggested default."""
        return questionary.text(
            "Mount point label (will mount at /mnt/<label>):",
            default=default or "",
        ).ask()
