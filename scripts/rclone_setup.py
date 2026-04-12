#!/usr/bin/env python3
"""
Interactive setup: declare the rclone cloud remote and path used for the
read-only media mount at /mnt/media.

Safe to re-run — shows existing values as defaults and only updates on change.

Run via: make rclone-setup
"""

import sys
from pathlib import Path

import yaml

ANSIBLE_DIR = Path(__file__).resolve().parent.parent / "ansible"
VARS_FILE = ANSIBLE_DIR / "group_vars" / "all" / "vars.yml"

RCLONE_CONFIG_HINT = """
  If you haven't configured the remote on the Pi yet, SSH in and run:

    ssh {user}@{host}
    rclone config

  Follow the prompts to add a new remote (e.g. pCloud OAuth).
  Once saved, re-run 'make rclone-setup' or 'make site --tags rclone'.
"""


def load_vars() -> dict:
    return yaml.safe_load(VARS_FILE.read_text()) or {}


def save_vars(data: dict) -> None:
    VARS_FILE.write_text(yaml.dump(data, default_flow_style=False))


def prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        value = input(f"{label}{suffix}: ").strip()
        if value:
            return value
        if default:
            return default
        print("  Value cannot be empty — try again.")


def main() -> None:
    print("=== rclone media mount setup ===\n")

    current = load_vars()
    existing_remote = current.get("rclone_remote", "")
    existing_path = current.get("rclone_remote_path", "")

    print("Declare the rclone remote and path to mount read-only at /mnt/media.\n")

    remote = prompt("Remote name (e.g. pcloud)", default=existing_remote)
    remote_path = prompt("Remote path  (e.g. Media)", default=existing_path)

    if remote == existing_remote and remote_path == existing_path:
        print("\nNo changes — remote is already configured.")
        print(f"  {remote}:{remote_path} → /mnt/media")
    else:
        current["rclone_remote"] = remote
        current["rclone_remote_path"] = remote_path
        save_vars(current)
        print(f"\nSaved: {remote}:{remote_path} → /mnt/media")

    # Derive SSH details from inventory for the hint message.
    try:
        import json
        import subprocess
        inv = subprocess.run(
            ["ansible-inventory", "--host", "rpi"],
            capture_output=True, text=True, cwd=ANSIBLE_DIR,
        )
        host_vars = json.loads(inv.stdout) if inv.returncode == 0 else {}
        host = host_vars.get("ansible_host", "<pi-ip>")
        user = host_vars.get("ansible_user", "<pi-user>")
    except Exception:
        host, user = "<pi-ip>", "<pi-user>"

    print(RCLONE_CONFIG_HINT.format(host=host, user=user))
    print("Next step: make site --tags rclone\n")


if __name__ == "__main__":
    main()
