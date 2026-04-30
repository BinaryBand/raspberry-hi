"""Preflight orchestration — dependency resolution, prompting, and persistence."""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Protocol

from linux_hi.adapters.prompt_handlers import PromptRegistryPort
from linux_hi.ansible.role_vars import role_required_vars
from linux_hi.vault.service import decrypt_vault_raw, encrypt_vault
from models import ANSIBLE_DATA, AppRegistryEntry, PreflightVarSpec, VaultSecretSpec

StoreData = dict[str, str]


class PreflightError(Exception):
    """Raised by the orchestration layer when preflight cannot proceed."""


class HostVarsPort(Protocol):
    """Port for reading and writing per-host Ansible variables."""

    def read(self, hostname: str) -> dict[str, object]:
        """Return the current host_vars for *hostname*."""
        ...

    def write(self, hostname: str, updates: dict[str, str]) -> None:
        """Persist *updates* into host_vars for *hostname*."""
        ...


class VaultPort(Protocol):
    """Port for reading and writing the encrypted vault."""

    def read(self) -> dict[str, object]:
        """Return the decrypted vault contents."""
        ...

    def write(self, data: dict[str, object]) -> None:
        """Encrypt and persist *data* as the vault contents."""
        ...


class AnsibleHostVarsStore:
    """Concrete HostVarsPort backed by ANSIBLE_DATA."""

    def read(self, hostname: str) -> dict[str, object]:
        """Return raw host_vars dict for *hostname*."""
        return ANSIBLE_DATA.read_host_vars_raw(hostname)

    def write(self, hostname: str, updates: dict[str, str]) -> None:
        """Write *updates* to host_vars for *hostname*."""
        ANSIBLE_DATA.write_host_vars_raw(hostname, updates)


class AnsibleVaultStore:
    """Concrete VaultPort backed by ansible-vault."""

    def read(self) -> dict[str, object]:
        """Return decrypted vault as a raw dict."""
        return decrypt_vault_raw()

    def write(self, data: dict[str, object]) -> None:
        """Encrypt and write *data* to the vault file."""
        encrypt_vault(data)


def _resolve_role_path(app: str) -> Path:
    """Return the role directory for *app* or raise PreflightError."""
    try:
        return ANSIBLE_DATA.role_path(app)
    except KeyError as exc:
        raise PreflightError(str(exc)) from exc


def load_preflight_spec(
    app: str, role_path: Path
) -> tuple[dict[str, PreflightVarSpec], list[VaultSecretSpec]]:
    """Return the prompt schema for *app* by merging registry metadata and role defaults."""
    entry: AppRegistryEntry = ANSIBLE_DATA.get_app_entry(app)
    required_vars = role_required_vars(role_path)
    vars_spec = {
        var: entry.preflight_vars.get(var, PreflightVarSpec(hint="")) for var in required_vars
    }
    return vars_spec, entry.vault_secrets


def _prompt_host_var(var_name: str, spec: PreflightVarSpec, registry: PromptRegistryPort) -> str:
    label = f"  {var_name}" + (f" ({spec.hint})" if spec.hint else "") + ":"
    value = registry.prompt(spec.type, label, spec.default or "")
    if not value:
        raise PreflightError(f"{var_name} is required. Aborting.")
    return value


def _prompt_secret(spec: VaultSecretSpec, registry: PromptRegistryPort) -> str:
    label = f"  {spec.key}" + (f" ({spec.label})" if spec.label else "") + ":"
    value = registry.prompt(spec.prompt_type, label)
    if not value:
        if spec.generate:
            generated = secrets.token_hex(32)
            print(f"  [AUTO]  Generated {spec.key}")
            return generated
        raise PreflightError(f"{spec.key} is required. Aborting.")
    return value


class PreflightOrchestrator:
    """Resolve app dependencies, prompt for missing vars and secrets, and persist them."""

    def __init__(self, registry: PromptRegistryPort, hv: HostVarsPort, vault: VaultPort) -> None:
        """Initialise with injected prompt registry and data stores."""
        self._registry = registry
        self._hv = hv
        self._vault = vault

    def run(self, app: str, hostname: str) -> None:
        """Run preflight for *app* and all its registry dependencies (depth-first)."""
        self._run_for(app, hostname, seen=set())

    def _run_for(self, app: str, hostname: str, seen: set[str]) -> None:
        if app in seen:
            return
        seen.add(app)
        entry = ANSIBLE_DATA.get_app_entry(app)
        for dep in entry.dependencies:
            self._run_for(dep, hostname, seen)
        role_path = _resolve_role_path(app)
        vars_spec, secrets_spec = load_preflight_spec(app, role_path)
        host_updates, secret_updates = self._collect(hostname, vars_spec, secrets_spec)
        self._write(hostname, host_updates, secret_updates)

    def _collect(
        self,
        hostname: str,
        vars_spec: dict[str, PreflightVarSpec],
        secrets_spec: list[VaultSecretSpec],
    ) -> tuple[StoreData, StoreData]:
        current_hv = self._hv.read(hostname)
        current_vault = self._vault.read()

        host_updates: StoreData = {}
        missing_vars = [name for name in vars_spec if not current_hv.get(name)]
        if missing_vars:
            print(f"  [WARN]  Missing required vars for '{hostname}' — please set them now.")
            for var_name in missing_vars:
                host_updates[var_name] = _prompt_host_var(
                    var_name, vars_spec[var_name], self._registry
                )

        secret_updates: StoreData = {}
        missing_secrets = [s for s in secrets_spec if not current_vault.get(s.key)]
        if missing_secrets:
            print("  [WARN]  Missing required vault secrets — please set them now.")
            for secret in missing_secrets:
                secret_updates[secret.key] = _prompt_secret(secret, self._registry)

        return host_updates, secret_updates

    def _write(self, hostname: str, host_updates: StoreData, secret_updates: StoreData) -> None:
        if host_updates:
            self._hv.write(hostname, host_updates)
            print(f"  [OK  ]  Wrote {len(host_updates)} var(s) for '{hostname}'")

        if secret_updates:
            data = self._vault.read()
            data.update(secret_updates)
            self._vault.write(data)
            print(f"  [OK  ]  Wrote {len(secret_updates)} vault secret(s)")
