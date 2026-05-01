"""RcloneRemoteHandler — prompt the operator to select a configured rclone remote."""

from __future__ import annotations

import sys

import questionary


class RcloneRemoteHandler:
    """Present vault-sourced rclone remotes as a selection prompt."""

    def prompt(self, label: str, default: str) -> str | None:
        """Select a configured rclone remote from the vault."""
        from linux_hi.services.vault import decrypt_vault
        from linux_hi.storage.rclone import list_remotes

        vault = decrypt_vault()
        remotes = list_remotes(vault.rclone_config or {})
        if not remotes:
            print("  [WARN]  No rclone remotes found in vault. Run 'make rclone' to configure one.")
            sys.exit(1)
        return questionary.select(label, choices=remotes).ask()
