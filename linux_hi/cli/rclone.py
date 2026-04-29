"""Configure project rclone remotes and persist the config to the Ansible vault."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import cast

import questionary

from linux_hi.process.exec import run_resolved
from linux_hi.storage.rclone import list_remotes, parse_rclone_ini
from linux_hi.vault.service import VAULT_FILE, decrypt_vault_raw, encrypt_vault

RCLONE_CONF = Path("config") / "rclone.conf"


def main() -> None:
    """Open rclone config for project remotes, then persist the config to the vault."""
    print(f"Opening rclone config (project file: {RCLONE_CONF})\n")
    RCLONE_CONF.parent.mkdir(exist_ok=True)
    RCLONE_CONF.touch()
    try:
        run_resolved(["rclone", "config", "--config", str(RCLONE_CONF)])
    except FileNotFoundError:
        sys.exit("rclone is not installed or not in PATH. Install it and retry.")

    if not RCLONE_CONF.exists() or not RCLONE_CONF.read_text().strip():
        sys.exit("  [FAIL]  No remotes configured — add at least one remote and retry.")

    config_text = RCLONE_CONF.read_text()
    parsed_new = parse_rclone_ini(config_text)
    new_remotes = list_remotes(parsed_new)
    if not new_remotes:
        sys.exit("  [FAIL]  No remotes found in config.")

    vault_data = decrypt_vault_raw()
    existing_raw = vault_data.get("rclone_config") or {}
    existing_config = cast(dict[str, dict[str, str]], existing_raw)
    if isinstance(existing_config, dict) and existing_config:
        existing_remotes = list_remotes(existing_config)
        print(f"  Vault remotes : {', '.join(existing_remotes)}")
        print(f"  Local remotes : {', '.join(new_remotes)}")
        if not questionary.confirm("Overwrite vault rclone config with local config?").ask():
            sys.exit("Aborted.")

    vault_data["rclone_config"] = parsed_new
    tmp = VAULT_FILE.with_suffix(".tmp")
    encrypt_vault(vault_data, output=tmp)
    os.replace(tmp, VAULT_FILE)

    names = ", ".join(new_remotes)
    print(f"  [OK  ]  Saved rclone config to vault ({len(new_remotes)} remote(s): {names})")


if __name__ == "__main__":
    main()
