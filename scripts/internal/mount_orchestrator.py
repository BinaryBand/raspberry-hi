"""Thin orchestration layer composing an InfoPort and a Prompter.

This keeps orchestration logic separate from discovery (InfoPort) and the
UI (Prompter) so both can be swapped or unit-tested independently.
"""

from __future__ import annotations

from scripts.utils.connection_types import RemoteConnection
from scripts.utils.info_port import InfoPort
from scripts.utils.prompter import Prompter


class MountOrchestrator:
    def __init__(self, info: InfoPort, prompter: Prompter) -> None:
        self.info = info
        self.prompter = prompter

    def mount_new_device(
        self, conn: RemoteConnection, label_hint: str | None = None
    ) -> tuple[str, str] | None:
        """
        Discover external devices, prompt the user, and return (device_path, label).

        - device_path: e.g. /dev/sdb1 (the selected device)
        - label: user-provided or default label (will be sanitized and used as mountpoint name)

        Returns None when the user cancels or no devices are available.
        Downstream code is responsible for label sanitization and for using UUID in fstab.
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
