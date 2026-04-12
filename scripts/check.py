#!/usr/bin/env python3
"""Validate prerequisites before running make site."""

import json
import os
import subprocess
import sys
from pathlib import Path

ANSIBLE_DIR = Path(__file__).parent.parent / "ansible"
SESSION_FILE = ANSIBLE_DIR / ".bw-session"


def check(label: str, ok: bool, fix: str = "") -> bool:
    mark = "OK  " if ok else "FAIL"
    print(f"  [{mark}]  {label}")
    if not ok and fix:
        print(f"          fix: {fix}")
    return ok


def main() -> None:
    print("Checking prerequisites...\n")
    all_ok = True

    # bw CLI installed
    bw_ok = subprocess.run(["which", "bw"], capture_output=True).returncode == 0
    all_ok &= check("bw CLI installed", bw_ok, "brew install bitwarden-cli")

    # Session file exists
    session = SESSION_FILE.read_text().strip() if SESSION_FILE.exists() else ""
    all_ok &= check("Bitwarden session file exists", bool(session), "make bw-login")

    # Vault unlocked
    if bw_ok and session:
        result = subprocess.run(
            ["bw", "status"],
            capture_output=True,
            text=True,
            env={**os.environ, "BW_SESSION": session},
        )
        try:
            unlocked = json.loads(result.stdout).get("status") == "unlocked"
        except (json.JSONDecodeError, AttributeError):
            unlocked = False
        all_ok &= check("Bitwarden vault unlocked", unlocked, "make bw-login")
    else:
        all_ok &= check("Bitwarden vault unlocked", False, "make bw-login")

    # Pi reachable
    ping = subprocess.run(
        ["ansible", "raspberry_pi", "-m", "ping", "-o"],
        capture_output=True,
        text=True,
        cwd=ANSIBLE_DIR,
    )
    pi_ok = "SUCCESS" in ping.stdout
    all_ok &= check(
        "Pi reachable",
        pi_ok,
        "Check SSH key and Pi address in ansible/inventory/hosts.ini",
    )

    print()
    if all_ok:
        print("All checks passed — ready to run: make site")
    else:
        print("Fix the issues above before running make site.")
        sys.exit(1)


if __name__ == "__main__":
    main()
