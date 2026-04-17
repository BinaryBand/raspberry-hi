#!/usr/bin/env python3
"""Generic pre-flight: prompt for any required-but-unset role vars before provisioning.

Each Ansible app role declares required variables by setting them to null (~) in
defaults/main.yml. This script reads that file, checks host_vars for the host,
and prompts for anything missing.

App-specific prompt hints live in scripts/preflights/<app>.py as VAR_HINTS dicts.
Adding a new app requires no changes here — only a null sentinel in defaults and
optionally a hints module.

Usage:
  HOST=rpi poetry run python scripts/preflight.py <app>
  HOST=rpi make minio  (called automatically via Makefile)
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Protocol

import questionary
from utils.ansible_utils import (
    ANSIBLE_DIR,
    read_host_vars_raw,
    role_required_vars,
    write_host_vars_raw,
)

# ---------------------------------------------------------------------------
# Ports
# ---------------------------------------------------------------------------


class VarRequirements(Protocol):
    def required(self) -> list[str]: ...
    def hint(self, var: str) -> str: ...
    def hidden(self, var: str) -> bool: ...


class VarStore(Protocol):
    def read(self, hostname: str) -> dict: ...
    def write(self, hostname: str, updates: dict) -> None: ...


# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------


class AnsibleRoleAdapter:
    """Reads required vars from a role's defaults/main.yml (null ~ = required).

    Loads prompt hints from scripts/preflights/<app>.py if the module exists.
    Falls back to an empty hint for any var not listed there.
    """

    def __init__(self, role_path: Path, app: str) -> None:
        self._role_path = role_path
        self._hints: dict[str, str] = {}
        try:
            mod = importlib.import_module(f"preflights.{app}")
            self._hints = getattr(mod, "VAR_HINTS", {})
        except ModuleNotFoundError:
            pass

    def required(self) -> list[str]:
        return role_required_vars(self._role_path)

    def hint(self, var: str) -> str:
        return self._hints.get(var, "")

    def hidden(self, var: str) -> bool:
        return False


class VaultSecretsAdapter:
    """Reads required vault secrets from preflights/<app>.py VAULT_SECRETS list."""

    def __init__(self, app: str) -> None:
        self._specs: list = []
        try:
            mod = importlib.import_module(f"preflights.{app}")
            self._specs = getattr(mod, "VAULT_SECRETS", [])
        except ModuleNotFoundError:
            pass

    def required(self) -> list[str]:
        return [s["key"] for s in self._specs]

    def hint(self, var: str) -> str:
        return next((s["label"] for s in self._specs if s["key"] == var), "")

    def hidden(self, var: str) -> bool:
        return next((s["hidden"] for s in self._specs if s["key"] == var), False)


class HostVarsAdapter:
    """Reads and writes host_vars/<hostname>.yml, preserving comments and formatting."""

    def read(self, hostname: str) -> dict:
        return read_host_vars_raw(hostname)

    def write(self, hostname: str, updates: dict) -> None:
        write_host_vars_raw(hostname, updates)


class VaultStore:
    """Reads and writes secrets to the Ansible vault."""

    def read(self, hostname: str) -> dict:
        from bootstrap import decrypt_vault_raw
        return decrypt_vault_raw()

    def write(self, hostname: str, updates: dict) -> None:
        from bootstrap import decrypt_vault_raw, encrypt_vault
        raw = decrypt_vault_raw()
        raw.update(updates)
        encrypt_vault(raw)


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------


def run_preflight(
    hostname: str,
    requirements: VarRequirements,
    store: VarStore,
) -> None:
    """Prompt for any required vars not yet set in host_vars for *hostname*."""
    required = requirements.required()
    if not required:
        return

    current = store.read(hostname)
    missing = [v for v in required if not current.get(v)]
    if not missing:
        return

    print(f"  [WARN]  Missing required vars for '{hostname}' — please set them now.")
    updates: dict = {}
    for var in missing:
        hint = requirements.hint(var)
        label = f"  {var}" + (f" ({hint})" if hint else "") + ":"
        value = (
            questionary.password(label).ask()
            if requirements.hidden(var)
            else questionary.text(label).ask()
        )
        if not value:
            sys.exit(f"  [FAIL]  {var} is required. Aborting.")
        updates[var] = value

    store.write(hostname, updates)
    print(f"  [OK  ]  Wrote {len(updates)} var(s) to host_vars/{hostname}.yml")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _resolve_role_path(app: str) -> Path:
    for base in ("apps", "roles"):
        path = ANSIBLE_DIR / base / app
        if path.exists():
            return path
    sys.exit(f"  [FAIL]  No role found for '{app}' under ansible/apps/ or ansible/roles/")


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("Usage: preflight.py <app>")
    app = sys.argv[1]
    hostname = os.environ.get("HOST", "rpi")

    # Vault secrets first — credentials must exist before Ansible runs.
    run_preflight(
        hostname=hostname,
        requirements=VaultSecretsAdapter(app),
        store=VaultStore(),
    )
    # Host vars second — infrastructure config specific to this host.
    run_preflight(
        hostname=hostname,
        requirements=AnsibleRoleAdapter(_resolve_role_path(app), app),
        store=HostVarsAdapter(),
    )


if __name__ == "__main__":
    main()
