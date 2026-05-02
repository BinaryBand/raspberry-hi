"""RcloneRemoteHandler — prompt for a configured remote and a path."""

from __future__ import annotations

import sys

import questionary


class RcloneRemoteHandler:
    """Present vault-sourced rclone remotes and prompt for a remote path."""

    @staticmethod
    def _split_default(default: str) -> tuple[str | None, str]:
        """Split default remote:path into (remote, path-default)."""
        if ":" not in default:
            return None, ""
        remote, path = default.split(":", 1)
        if not remote:
            return None, path
        return remote, path.lstrip("/")

    def prompt(self, label: str, default: str) -> str | None:
        """Select a configured rclone remote then prompt for a path inside it."""
        from linux_hi.services.vault import decrypt_vault
        from linux_hi.storage.rclone import list_remotes

        vault = decrypt_vault()
        remotes = list_remotes(vault.rclone_config or {})
        if not remotes:
            print("  [WARN]  No rclone remotes found in vault. Run 'make rclone' to configure one.")
            sys.exit(1)

        default_remote, default_path = self._split_default(default)
        if default_remote in remotes:
            remote = questionary.select(label, choices=remotes, default=default_remote).ask()
        else:
            remote = questionary.select(label, choices=remotes).ask()
        if remote is None:
            return None

        path = questionary.text(
            f"Path within '{remote}' (leave blank for remote root)",
            default=default_path,
        ).ask()
        if path is None:
            return None

        normalised_path = path.strip().strip("/")
        if normalised_path:
            return f"{remote}:{normalised_path}"
        return f"{remote}:"
