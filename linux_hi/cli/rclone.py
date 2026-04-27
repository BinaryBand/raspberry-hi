"""Configure project rclone remotes and persist the config to the Ansible vault."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import questionary

from linux_hi.orchestration.rclone import RcloneSetupController
from linux_hi.process.exec import run_resolved
from linux_hi.vault.service import VAULT_FILE, decrypt_vault_raw, encrypt_vault

RCLONE_CONF = Path("config") / "rclone.conf"


class _VaultAdapter:
    def read(self) -> dict[str, object]:
        return decrypt_vault_raw()

    def write(self, data: dict[str, object]) -> None:
        tmp = VAULT_FILE.with_suffix(".tmp")
        encrypt_vault(data, output=tmp)
        os.replace(tmp, VAULT_FILE)


class _QuestionaryConfirm:
    def confirm_overwrite(self, existing: list[str], incoming: list[str]) -> bool:
        print(f"  Vault remotes : {', '.join(existing)}")
        print(f"  Local remotes : {', '.join(incoming)}")
        result = questionary.confirm("Overwrite vault rclone config with local config?").ask()
        return bool(result)


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
    controller = RcloneSetupController(
        vault=_VaultAdapter(),
        prompter=_QuestionaryConfirm(),
    )

    try:
        saved = controller.run(config_text)
    except ValueError as exc:
        sys.exit(f"  [FAIL]  {exc}")

    print(f"  [OK  ]  Saved rclone config to vault ({len(saved)} remote(s): {', '.join(saved)})")


if __name__ == "__main__":
    main()
