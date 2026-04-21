"""Thin orchestration layer composing an InfoPort and a Prompter.

This keeps orchestration logic separate from discovery (InfoPort) and the
UI (Prompter) so both can be swapped or unit-tested independently.
"""

from __future__ import annotations

from utils.connection_types import RemoteConnection
from utils.info_port import InfoPort
from utils.prompter import Prompter


class MountOrchestrator:
    def __init__(self, info: InfoPort, prompter: Prompter) -> None:
        self.info = info
        self.prompter = prompter

    def mount_new_device(
        self, conn: RemoteConnection, label_hint: str | None = None
    ) -> tuple[str, str] | None:
        """Discover external devices, prompt the user, and return (device, label).

        Returns ``None`` when the user cancels or no devices are available.
        """
        devices = self.info.list_devices(conn)
        if not devices:
            return None

        selected = self.prompter.choose_device(devices)
        if not selected:
            return None

        # Prefer explicit hint, then partition label, then device name.
        default_label = (
            label_hint or getattr(selected, "label", None) or getattr(selected, "name", None)
        )
        label = self.prompter.ask_label(default_label)
        if not label:
            return None

        device_path = f"/dev/{selected.name}"
        return device_path, label
