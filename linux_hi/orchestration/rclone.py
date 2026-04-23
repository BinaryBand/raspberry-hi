"""Orchestration for the rclone remote setup workflow."""

from __future__ import annotations

import sys
from typing import Protocol, cast


class VaultPort(Protocol):
    """Port for reading and writing vault-backed config data."""

    def read(self) -> dict[str, object]:
        """Return the current vault payload."""
        ...

    def write(self, data: dict[str, object]) -> None:
        """Persist an updated vault payload."""
        ...


class ConfirmPrompter(Protocol):
    """Port for destructive-overwrite confirmation prompts."""

    def confirm_overwrite(self, existing: list[str], incoming: list[str]) -> bool:
        """Confirm whether incoming remotes may replace existing ones."""
        ...


class RcloneSetupController:
    """Saves a local rclone config into the vault, prompting on overwrite."""

    def __init__(self, vault: VaultPort, prompter: ConfirmPrompter) -> None:
        """Store the vault and prompt ports used by the workflow."""
        self._vault = vault
        self._prompter = prompter

    def run(self, config_text: str) -> list[str]:
        """Persist config_text in the vault and return the remote names saved."""
        from linux_hi.storage.rclone import list_remotes, parse_rclone_ini

        parsed_new = parse_rclone_ini(config_text)
        new_remotes = list_remotes(parsed_new)
        if not new_remotes:
            raise ValueError("No remotes found in config.")

        vault_data = self._vault.read()
        # vault_data comes from an untyped backend; cast into the expected
        # mapping so the type checker accepts it when passed to list_remotes().
        existing_raw = vault_data.get("rclone_config") or {}
        existing_config = cast(dict[str, dict[str, str]], existing_raw)

        if not isinstance(existing_config, dict):
            existing_config = {}

        if existing_config:
            existing_remotes = list_remotes(existing_config)
            if not self._prompter.confirm_overwrite(existing_remotes, new_remotes):
                sys.exit("Aborted.")

        # Persist the structured mapping into the vault
        vault_data["rclone_config"] = parsed_new
        self._vault.write(vault_data)
        return new_remotes
