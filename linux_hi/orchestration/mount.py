"""Thin orchestration layer composing an InfoPort and a Prompter."""

from __future__ import annotations

from linux_hi.adapters.connection_types import RemoteConnection
from linux_hi.adapters.info_port import InfoPort
from linux_hi.adapters.prompter import Prompter


class MountOrchestrator:
    """Coordinate device discovery and user prompts for interactive mounts."""

    def __init__(self, info: InfoPort, prompter: Prompter) -> None:
        """Store the ports required to discover devices and prompt the user."""
        self.info = info
        self.prompter = prompter

    def mount_new_device(
        self, conn: RemoteConnection, label_hint: str | None = None
    ) -> tuple[str, str] | None:
        """Discover external devices, prompt the user, and return the selected mount info."""
        devices = self.info.list_devices(conn)
        if not devices:
            return None

        selected = self.prompter.choose_device(devices)
        if not selected:
            return None

        default_label = label_hint or selected.label or selected.name
        label = self.prompter.ask_label(default_label)
        if not label:
            return None

        return f"/dev/{selected.name}", label
