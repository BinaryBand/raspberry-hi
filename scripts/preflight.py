#!/usr/bin/env python3
"""Generic pre-flight: prompt for any required-but-unset role vars before provisioning.

Each Ansible app role declares required variables by setting them to null (~) in
defaults/main.yml. This script reads that file, checks host_vars for the host,
and prompts for anything missing.

App-specific prompt hints and vault secret definitions live in
ansible/apps/<app>/preflight.yml. Adding a new app requires no changes here —
only a null sentinel in defaults and optionally a preflight.yml in the role.

Usage:
  HOST=rpi poetry run python scripts/preflight.py <app>
  HOST=rpi make minio  (called automatically via Makefile)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, cast

import questionary
import yaml
from utils.ansible_utils import (
    ANSIBLE_DIR,
    read_host_vars_raw,
    role_required_vars,
    write_host_vars_raw,
)
from utils.yaml_utils import yaml_mapping

if TYPE_CHECKING:
    from bootstrap import SecretSpec


StoreData = dict[str, Any]

# ---------------------------------------------------------------------------
# Ports
# ---------------------------------------------------------------------------


class VarRequirements(Protocol):
    def required(self) -> list[str]: ...
    def hint(self, var: str) -> str: ...
    def hidden(self, var: str) -> bool: ...
    def default(self, var: str) -> str | None: ...


class VarStore(Protocol):
    def read(self, hostname: str) -> StoreData: ...
    def write(self, hostname: str, updates: StoreData) -> None: ...


# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------


class AnsibleRoleAdapter:
    """Reads required vars from a role's defaults/main.yml (null ~ = required).

    Loads prompt hints from the role's preflight.yml if present.
    Falls back to an empty hint for any var not listed there.
    """

    def __init__(self, role_path: Path) -> None:
        self._role_path = role_path
        self._hints: dict[str, str] = {}
        self._defaults: dict[str, str] = {}
        preflight_path = role_path / "preflight.yml"
        if preflight_path.exists():
            data = yaml_mapping(yaml.safe_load(preflight_path.read_text()), source=preflight_path)
            for k, v in cast("dict[str, Any]", data.get("var_hints", {})).items():
                if isinstance(v, dict):
                    hint_entry = cast("dict[str, str]", v)
                    self._hints[k] = hint_entry.get("hint", "")
                    if d := hint_entry.get("default"):
                        self._defaults[k] = d
                else:
                    self._hints[k] = v

    def required(self) -> list[str]:
        return role_required_vars(self._role_path)

    def hint(self, var: str) -> str:
        return self._hints.get(var, "")

    def hidden(self, var: str) -> bool:
        return False

    def default(self, var: str) -> str | None:
        return self._defaults.get(var)


class VaultSecretsAdapter:
    """Reads required vault secrets from the role's preflight.yml."""

    def __init__(self, role_path: Path) -> None:
        self._specs: list[SecretSpec] = []
        preflight_path = role_path / "preflight.yml"
        if preflight_path.exists():
            data = yaml_mapping(yaml.safe_load(preflight_path.read_text()), source=preflight_path)
            self._specs = cast("list[SecretSpec]", data.get("vault_secrets", []))

    def required(self) -> list[str]:
        return [s["key"] for s in self._specs]

    def hint(self, var: str) -> str:
        return next((s["label"] for s in self._specs if s["key"] == var), "")

    def hidden(self, var: str) -> bool:
        return next((s["hidden"] for s in self._specs if s["key"] == var), False)

    def default(self, var: str) -> str | None:
        return None


class HostVarsAdapter:
    """Reads and writes host_vars/<hostname>.yml, preserving comments and formatting."""

    def read(self, hostname: str) -> StoreData:
        return read_host_vars_raw(hostname)

    def write(self, hostname: str, updates: StoreData) -> None:
        write_host_vars_raw(hostname, updates)


class VaultStore:
    """Reads and writes secrets to the Ansible vault."""

    def read(self, hostname: str) -> StoreData:
        from bootstrap import decrypt_vault_raw

        return decrypt_vault_raw()

    def write(self, hostname: str, updates: StoreData) -> None:
        from bootstrap import VAULT_FILE, decrypt_vault_raw, encrypt_vault

        raw = decrypt_vault_raw()
        raw.update(updates)
        tmp = VAULT_FILE.with_suffix(".tmp")
        encrypt_vault(raw, output=tmp)
        os.replace(tmp, VAULT_FILE)


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
    updates: StoreData = {}
    for var in missing:
        hint = requirements.hint(var)
        label = f"  {var}" + (f" ({hint})" if hint else "") + ":"
        value = (
            questionary.password(label).ask()
            if requirements.hidden(var)
            else questionary.text(label, default=requirements.default(var) or "").ask()
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
    hostname = os.environ.get("HOST")
    if not hostname:
        sys.exit("HOST is required — set HOST=<inventory-alias> and retry.")
    role_path = _resolve_role_path(app)

    # Vault secrets first — credentials must exist before Ansible runs.
    run_preflight(
        hostname=hostname,
        requirements=VaultSecretsAdapter(role_path),
        store=VaultStore(),
    )
    # Host vars second — infrastructure config specific to this host.
    run_preflight(
        hostname=hostname,
        requirements=AnsibleRoleAdapter(role_path),
        store=HostVarsAdapter(),
    )


if __name__ == "__main__":
    main()
