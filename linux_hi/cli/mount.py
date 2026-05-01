"""Interactively pick and mount an external storage device on a remote host."""

from __future__ import annotations

import io
import os
import re
import shlex
import sys

from linux_hi.adapters.info_port import RemoteInfoPort
from linux_hi.adapters.prompter import QuestionaryPrompter
from linux_hi.ansible.connection import make_connection
from linux_hi.models import ANSIBLE_DATA
from linux_hi.orchestration.mount import MountOrchestrator
from linux_hi.storage.devices import get_device_uuid
from linux_hi.vault.service import decrypt_vault


def _become_password(hostname: str) -> str:
    """Read the become (sudo) password for *hostname* from the vault."""
    secrets = decrypt_vault()
    pwd = (secrets.become_passwords or {}).get(hostname, "")
    if not pwd:
        sys.exit(f"No become password in vault for '{hostname}'. Run: make bootstrap")
    return pwd


def main() -> None:
    """Mount a selected device and append an fstab entry on the remote host."""
    hostname = os.environ.get("HOST")
    if not hostname:
        sys.exit("HOST is required — set HOST=<inventory-alias> and retry.")
    hvars = ANSIBLE_DATA.host_vars(hostname)
    become_pwd = _become_password(hostname)
    conn = make_connection(hvars, become_password=become_pwd)

    orchestrator = MountOrchestrator(info=RemoteInfoPort(), prompter=QuestionaryPrompter())
    result = orchestrator.mount_new_device(conn)
    if not result:
        sys.exit("No device selected.")

    device, label = result
    safe_label = re.sub(r"[^a-zA-Z0-9_-]", "_", label).lstrip("_").rstrip("_")
    if not safe_label:
        sys.exit("Invalid mount label after sanitization.")
    mount_point = f"/mnt/{safe_label}"
    dev = shlex.quote(device)
    mp = shlex.quote(mount_point)

    conn.sudo(f"mkdir -p {mp}", hide=True)
    conn.sudo(f"mount {dev} {mp}", hide=True)

    uuid = get_device_uuid(conn, device)
    fstab = conn.sudo("cat /etc/fstab", hide=True).stdout
    entry = None
    if uuid:
        uuid_line = f"UUID={uuid} {mount_point} auto defaults,nofail 0 0\n"
        if f"UUID={uuid}" not in fstab:
            entry = uuid_line
    else:
        dev_line = f"{device} {mount_point} auto defaults,nofail 0 0\n"
        if device not in fstab:
            entry = dev_line
    if entry:
        conn.sudo("tee -a /etc/fstab", in_stream=io.StringIO(entry), hide=True)

    print(f"Mounted {device} at {mount_point}.")


if __name__ == "__main__":
    main()
