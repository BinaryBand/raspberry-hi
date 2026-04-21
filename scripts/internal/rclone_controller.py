"""Orchestration for the rclone remote setup workflow.

Reads a local rclone.conf text, confirms with the user when overwriting an
existing vault entry, and writes the config blob into the Ansible vault so
the rclone Ansible role can deploy it to any host.
"""

from __future__ import annotations

import sys
from typing import Protocol


class VaultPort(Protocol):
    """Read/write access to the Ansible vault key-value store."""

    def read(self) -> dict[str, object]: ...

    def write(self, data: dict[str, object]) -> None: ...


class ConfirmPrompter(Protocol):
    """Prompt the operator before destructive vault overwrites."""

    def confirm_overwrite(self, existing: list[str], incoming: list[str]) -> bool: ...


class RcloneSetupController:
    """Saves a local rclone config into the vault, prompting on overwrite."""

    def __init__(self, vault: VaultPort, prompter: ConfirmPrompter) -> None:
        self._vault = vault
        self._prompter = prompter

    def run(self, config_text: str) -> list[str]:
        """Persist *config_text* in the vault and return the list of remote names saved.

        Raises ``ValueError`` when *config_text* contains no remote sections.
        Calls ``sys.exit`` when the operator declines an overwrite.
        """
        from scripts.utils.rclone_utils import list_remotes

        new_remotes = list_remotes(config_text)
        if not new_remotes:
            raise ValueError("No remotes found in config.")

        vault_data = self._vault.read()
        existing_config = str(vault_data.get("rclone_config") or "")

        if existing_config:
            existing_remotes = list_remotes(existing_config)
            if not self._prompter.confirm_overwrite(existing_remotes, new_remotes):
                sys.exit("Aborted.")

        vault_data["rclone_config"] = config_text
        self._vault.write(vault_data)
        return new_remotes
