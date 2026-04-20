#!/usr/bin/env python3
"""Generic pre-flight: prompt for any required-but-unset role vars before provisioning.

Each Ansible app role declares required variables by setting them to null (~) in
defaults/main.yml. This script reads that file, checks host_vars for the host,
and prompts for anything missing.

App-specific prompt hints and vault secret definitions live in
ansible/registry.yml. Adding a new app requires no code changes here — only a
null sentinel in defaults and registry metadata.

Usage:
  HOST=rpi poetry run python scripts/preflight.py <app>
  HOST=rpi make minio  (called automatically via Makefile)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import questionary
from utils.ansible_utils import (
    ANSIBLE_DIR,
    get_app_entry,
    read_host_vars_raw,
    role_required_vars,
    write_host_vars_raw,
)

from models import AppRegistryEntry, PreflightVarSpec, VaultSecretSpec

StoreData = dict[str, Any]


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------


def _pick_rclone_remote(label: str) -> str | None:
    """Present existing vault rclone remotes as a selection prompt."""
    from bootstrap import decrypt_vault_raw
    from utils.rclone_utils import list_remotes

    raw = decrypt_vault_raw()
    config_text = str(raw.get("rclone_config") or "")
    remotes = list_remotes(config_text)

    if not remotes:
        print("  [WARN]  No rclone remotes found in vault. Run 'make rclone' to configure one.")
        sys.exit(1)

    return questionary.select(label, choices=remotes).ask()


def load_preflight_spec(
    app: str, role_path: Path
) -> tuple[dict[str, PreflightVarSpec], list[VaultSecretSpec]]:
    """Return the prompt schema for *app* by combining registry metadata and role defaults."""
    entry: AppRegistryEntry = get_app_entry(app)
    required_vars = role_required_vars(role_path)
    var_hints = entry.preflight_vars or {}
    vars_spec = {var: var_hints.get(var, PreflightVarSpec(hint="")) for var in required_vars}
    secrets_spec = entry.vault_secrets or []
    return vars_spec, secrets_spec


def _prompt_host_var(var_name: str, spec: PreflightVarSpec) -> str:
    label = f"  {var_name}" + (f" ({spec.hint})" if spec.hint else "") + ":"
    if getattr(spec, "type", None) == "rclone_remote":
        value = _pick_rclone_remote(label)
    else:
        value = questionary.text(label, default=getattr(spec, "default", None) or "").ask()
    if not value:
        sys.exit(f"  [FAIL]  {var_name} is required. Aborting.")
    return value


def _prompt_secret(spec: VaultSecretSpec) -> str:
    label = f"  {spec.key}" + (f" ({spec.label})" if spec.label else "") + ":"
    if spec.hidden:
        value = questionary.password(label).ask()
    else:
        value = questionary.text(label).ask()
    if not value:
        sys.exit(f"  [FAIL]  {spec.key} is required. Aborting.")
    return value


def collect_preflight_updates(
    hostname: str,
    vars_spec: dict[str, PreflightVarSpec],
    secrets_spec: list[VaultSecretSpec],
) -> tuple[StoreData, StoreData]:
    """Prompt for any missing host vars and vault secrets and return the updates."""
    from bootstrap import decrypt_vault_raw

    current_host_vars = read_host_vars_raw(hostname)
    current_vault = decrypt_vault_raw()

    host_updates: StoreData = {}
    missing_vars = [name for name in vars_spec if not current_host_vars.get(name)]
    if missing_vars:
        print(f"  [WARN]  Missing required vars for '{hostname}' — please set them now.")
        for var_name in missing_vars:
            host_updates[var_name] = _prompt_host_var(var_name, vars_spec[var_name])

    secret_updates: StoreData = {}
    missing_secrets = [secret for secret in secrets_spec if not current_vault.get(secret.key)]
    if missing_secrets:
        print("  [WARN]  Missing required vault secrets — please set them now.")
        for secret in missing_secrets:
            secret_updates[secret.key] = _prompt_secret(secret)

    return host_updates, secret_updates


def write_preflight_updates(
    hostname: str,
    host_updates: StoreData,
    secret_updates: StoreData,
) -> None:
    """Persist any prompted host vars and vault secrets."""
    if host_updates:
        write_host_vars_raw(hostname, host_updates)
        print(f"  [OK  ]  Wrote {len(host_updates)} var(s) for '{hostname}'")

    if secret_updates:
        from bootstrap import VAULT_FILE, decrypt_vault_raw, encrypt_vault

        raw = decrypt_vault_raw()
        raw.update(secret_updates)
        tmp = VAULT_FILE.with_suffix(".tmp")
        encrypt_vault(raw, output=tmp)
        os.replace(tmp, VAULT_FILE)
        print(f"  [OK  ]  Wrote {len(secret_updates)} vault secret(s)")


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
    vars_spec, secrets_spec = load_preflight_spec(app, role_path)
    host_updates, secret_updates = collect_preflight_updates(hostname, vars_spec, secrets_spec)
    write_preflight_updates(hostname, host_updates, secret_updates)


if __name__ == "__main__":
    main()
