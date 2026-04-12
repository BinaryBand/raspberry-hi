#!/usr/bin/env python3
"""
Authenticate the Bitwarden CLI and save the session token to ansible/.bw-session.

First-time setup:
  1. In Bitwarden: Account Settings → Security → API Key
  2. Export the values before running:
       export BW_CLIENTID="user.xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
       export BW_CLIENTSECRET="xxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  3. Run: make bw-login
"""

import getpass
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
SESSION_FILE = SCRIPTS_DIR.parent / "ansible" / ".bw-session"


def run(cmd, env=None, check=True):
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
        check=check,
    )


def get_status():
    result = run(["bw", "status"], check=False)
    try:
        return json.loads(result.stdout).get("status", "unauthenticated")
    except json.JSONDecodeError:
        return "unauthenticated"


def ensure_logged_in(status):
    if status != "unauthenticated":
        return

    client_id = os.environ.get("BW_CLIENTID")
    client_secret = os.environ.get("BW_CLIENTSECRET")

    if not client_id or not client_secret:
        print(
            "ERROR: BW_CLIENTID and BW_CLIENTSECRET must be set.\n"
            "Get your API key from: Bitwarden → Account Settings → Security → API Key",
            file=sys.stderr,
        )
        sys.exit(1)

    print("Logging in with API key...")
    result = run(["bw", "login", "--apikey"], check=False)
    if result.returncode != 0:
        print(f"Login failed:\n{result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    print("Logged in.")


def unlock():
    password = getpass.getpass("Bitwarden master password: ")
    result = run(
        ["bw", "unlock", "--passwordenv", "BW_PASSWORD"],
        env={"BW_PASSWORD": password},
        check=False,
    )
    if result.returncode != 0:
        print(f"Unlock failed:\n{result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)

    match = re.search(r'BW_SESSION="([^"]+)"', result.stdout)
    if not match:
        print("Could not extract session token from bw output.", file=sys.stderr)
        sys.exit(1)

    return match.group(1)


def save_session(token):
    SESSION_FILE.write_text(token)
    SESSION_FILE.chmod(0o600)
    print(f"Session saved to {SESSION_FILE}")


def main():
    try:
        run(["which", "bw"])
    except subprocess.CalledProcessError:
        print(
            "ERROR: bw CLI not found. Install with: brew install bitwarden-cli",
            file=sys.stderr,
        )
        sys.exit(1)

    status = get_status()

    if status == "unlocked":
        print("Vault already unlocked — refreshing session.")

    ensure_logged_in(status)
    token = unlock()
    save_session(token)


if __name__ == "__main__":
    main()
