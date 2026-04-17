#!/usr/bin/env python3
"""Interactively pick and mount an external storage device on a remote host.

Reads connection details from the Ansible inventory and the become password
from the vault — no Ansible playbook involvement.

Usage:
  HOST=rpi make mount
"""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path
from typing import cast

from fabric import Config, Connection
from mount_orchestrator import MountOrchestrator
from utils.ansible_utils import ANSIBLE_DIR, ROOT, inventory_host_vars
from utils.info_port import RemoteInfoPort
from utils.prompter import QuestionaryPrompter


def _become_password(hostname: str) -> str:
    """Read the become (sudo) password for *hostname* from the vault."""
    sys.path.insert(0, str(ANSIBLE_DIR.parent / "scripts"))
    from bootstrap import decrypt_vault_raw  # noqa: PLC0415

    raw = decrypt_vault_raw()
    become_passwords = cast(dict[str, str], raw.get("become_passwords") or {})
    pwd = become_passwords.get(hostname, "")
    if not pwd:
        sys.exit(f"No become password in vault for '{hostname}'. Run: make bootstrap")
    return pwd


def main() -> None:
    hostname = os.environ.get("HOST", "rpi")
    hvars = inventory_host_vars(hostname)
    become_pwd = _become_password(hostname)

    connect_kwargs: dict[str, str] = {}
    if hvars.ansible_ssh_private_key_file:
        key_path = Path(hvars.ansible_ssh_private_key_file)
        if not key_path.is_absolute():
            key_path = ROOT / key_path
        connect_kwargs["key_filename"] = str(key_path)

    conn = Connection(
        host=hvars.ansible_host,
        user=hvars.ansible_user,
        port=hvars.ansible_port or 22,
        connect_kwargs=connect_kwargs,
        config=Config(overrides={"sudo": {"password": become_pwd}}),
    )

    orchestrator = MountOrchestrator(info=RemoteInfoPort(), prompter=QuestionaryPrompter())
    result = orchestrator.mount_new_device(conn)
    if not result:
        sys.exit("No device selected.")

    device, label = result
    mount_point = f"/mnt/{label}"

    conn.sudo(f"mkdir -p {mount_point}", hide=True)
    conn.sudo(f"mount {device} {mount_point}", hide=True)

    # Append to fstab only if this device isn't already listed.
    fstab = conn.sudo("cat /etc/fstab", hide=True).stdout
    if device not in fstab:
        entry = f"{device} {mount_point} auto defaults,nofail 0 0\n"
        conn.sudo("tee -a /etc/fstab", in_stream=io.StringIO(entry), hide=True)

    print(f"Mounted {device} at {mount_point}.")


if __name__ == "__main__":
    main()
