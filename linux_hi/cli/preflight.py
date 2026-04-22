"""Registry-driven preflight prompting before provisioning."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import questionary

from linux_hi.ansible.inventory import require_inventory_host
from linux_hi.ansible.role_vars import role_required_vars
from linux_hi.vault.service import VAULT_FILE, decrypt_vault_raw, replace_vault_data
from models import ANSIBLE_DATA, AppRegistryEntry, PreflightVarSpec, VaultSecretSpec

StoreData = dict[str, str]


def _pick_rclone_remote(label: str) -> str | None:
    """Present existing vault rclone remotes as a selection prompt."""
    from linux_hi.storage.rclone import list_remotes

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
    entry: AppRegistryEntry = ANSIBLE_DATA.get_app_entry(app)
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
    current_host_vars = ANSIBLE_DATA.read_host_vars_raw(hostname)
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
        ANSIBLE_DATA.write_host_vars_raw(hostname, host_updates)
        print(f"  [OK  ]  Wrote {len(host_updates)} var(s) for '{hostname}'")

    if secret_updates:
        replace_vault_data(secret_updates, vault_file=VAULT_FILE)
        print(f"  [OK  ]  Wrote {len(secret_updates)} vault secret(s)")


def _resolve_role_path(app: str) -> Path:
    """Return the repo role path for *app* or terminate with a CLI-friendly error."""
    try:
        return ANSIBLE_DATA.role_path(app)
    except KeyError as exc:
        sys.exit(f"  [FAIL]  {exc}")


def main(argv: list[str] | None = None) -> None:
    """Prompt for missing role vars and secrets for a single app."""
    args = argv if argv is not None else sys.argv[1:]
    if len(args) < 1:
        sys.exit("Usage: preflight.py <app>")
    app = args[0]
    hostname = os.environ.get("HOST")
    if not hostname:
        sys.exit("HOST is required — set HOST=<inventory-alias> and retry.")
    hostname = require_inventory_host(hostname)
    role_path = _resolve_role_path(app)
    vars_spec, secrets_spec = load_preflight_spec(app, role_path)
    host_updates, secret_updates = collect_preflight_updates(hostname, vars_spec, secrets_spec)
    write_preflight_updates(hostname, host_updates, secret_updates)


if __name__ == "__main__":
    main()
