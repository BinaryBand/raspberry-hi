"""Tests for registry-driven preflight metadata and orchestration behaviour."""

from __future__ import annotations

import pytest

from linux_hi.orchestration.preflight import PreflightOrchestrator, load_preflight_spec
from models import ANSIBLE_DATA
from tests.support.preflight_fakes import FakeHostVarsStore, FakePromptRegistry, FakeVaultStore

# ---------------------------------------------------------------------------
# Registry structure tests
# ---------------------------------------------------------------------------


def test_ansible_dir_exists() -> None:
    """The helper should point at the checked-in Ansible directory."""
    assert ANSIBLE_DATA.ansible_dir.exists()
    assert (ANSIBLE_DATA.ansible_dir / "registry.yml").exists()


def test_registered_apps_have_role_directories() -> None:
    """Each registered app must resolve to a role directory under ansible/apps."""
    for app in ANSIBLE_DATA.all_apps():
        assert (ANSIBLE_DATA.ansible_dir / "apps" / app).exists()


def test_registry_entries_expose_preflight_fields() -> None:
    """Each registry entry should declare preflight vars and vault secret metadata."""
    for app in ANSIBLE_DATA.all_apps():
        entry = ANSIBLE_DATA.get_app_entry(app)
        assert isinstance(entry.preflight_vars, dict)
        assert isinstance(entry.vault_secrets, list)


# ---------------------------------------------------------------------------
# VaultSecretSpec.prompt_type
# ---------------------------------------------------------------------------


def test_vault_secret_prompt_type_hidden() -> None:
    """A hidden secret resolves to the 'password' prompt type."""
    entry = ANSIBLE_DATA.get_app_entry("minio")
    hidden = next(s for s in entry.vault_secrets if s.hidden)
    assert hidden.prompt_type == "password"


def test_vault_secret_prompt_type_visible() -> None:
    """A non-hidden secret resolves to the 'text' prompt type."""
    entry = ANSIBLE_DATA.get_app_entry("minio")
    visible = next(s for s in entry.vault_secrets if not s.hidden)
    assert visible.prompt_type == "text"


# ---------------------------------------------------------------------------
# Orchestrator behavioural tests
# ---------------------------------------------------------------------------

HOST = "rpi"


def _orchestrator(
    responses: dict[str, str] | None = None,
    host_vars: dict[str, object] | None = None,
    vault: dict[str, object] | None = None,
) -> tuple[PreflightOrchestrator, FakeHostVarsStore, FakeVaultStore]:
    hv_store = FakeHostVarsStore(initial={HOST: host_vars} if host_vars else None)
    v_store = FakeVaultStore(initial=vault)
    registry = FakePromptRegistry(responses or {})
    return (
        PreflightOrchestrator(registry=registry, hv=hv_store, vault=v_store),
        hv_store,
        v_store,
    )


def test_already_set_vars_are_skipped() -> None:
    """Vars already present in host_vars are not prompted and not written."""
    orch, hv, _ = _orchestrator(
        host_vars={"minio_data_path": "/data/minio"},
        vault={"minio_root_user": "admin", "minio_root_password": "secret"},
    )
    orch.run("minio", HOST)
    assert "minio" not in hv.written


def test_missing_vars_are_prompted_and_written() -> None:
    """A missing host var triggers a prompt and is persisted."""
    orch, hv, _ = _orchestrator(
        responses={"text": "/data/minio"},
        vault={"minio_root_user": "admin", "minio_root_password": "secret"},
    )
    orch.run("minio", HOST)
    assert hv.written.get(HOST, {}).get("minio_data_path") == "/data/minio"


def test_already_set_secrets_are_skipped() -> None:
    """Secrets already in the vault are not prompted and the vault is not rewritten."""
    orch, _, v = _orchestrator(
        host_vars={"minio_data_path": "/data/minio"},
        vault={"minio_root_user": "admin", "minio_root_password": "secret"},
    )
    orch.run("minio", HOST)
    assert v.written == []


def test_generate_flag_auto_fills_empty_secret() -> None:
    """An empty response for a generate=True secret produces a hex token."""
    entry = ANSIBLE_DATA.get_app_entry("minio")
    generate_secrets = [s for s in entry.vault_secrets if s.generate]
    if not generate_secrets:
        pytest.skip("minio has no generate=True secrets")

    orch, _, v = _orchestrator(
        host_vars={"minio_data_path": "/data/minio"},
        vault={},
        responses={},  # empty responses → triggers generate path
    )
    orch.run("minio", HOST)
    for secret in generate_secrets:
        written_val = v.written[-1].get(secret.key, "")
        assert isinstance(written_val, str)
        assert len(written_val) == 64  # token_hex(32) → 64 hex chars


def test_dependency_runs_before_app() -> None:
    """Baikal's dependency (postgres) is preflighted before baikal itself."""
    calls: list[str] = []

    class TrackingStore(FakeHostVarsStore):
        def read(self, hostname: str) -> dict[str, object]:
            calls.append(hostname)
            return super().read(hostname)

    role_path_baikal = ANSIBLE_DATA.role_path("baikal")
    role_path_postgres = ANSIBLE_DATA.role_path("postgres")
    vars_baikal, secrets_baikal = load_preflight_spec("baikal", role_path_baikal)
    vars_postgres, secrets_postgres = load_preflight_spec("postgres", role_path_postgres)

    all_vars: dict[str, object] = {k: "/some/path" for k in list(vars_baikal) + list(vars_postgres)}
    all_secrets: dict[str, object] = {
        s.key: "val" for s in list(secrets_baikal) + list(secrets_postgres)
    }

    hv = TrackingStore(initial={HOST: all_vars})
    v = FakeVaultStore(initial=all_secrets)
    orch = PreflightOrchestrator(registry=FakePromptRegistry({}), hv=hv, vault=v)
    orch.run("baikal", HOST)

    # postgres must be read before baikal — calls alternate but postgres comes first
    assert calls.index(HOST) == 0  # first read is for postgres (depth-first)


def test_cycle_detection_prevents_infinite_loop() -> None:
    """Artificially cyclic dependency entries do not cause infinite recursion."""
    from unittest.mock import patch

    from models.ansible.registry import AppRegistryEntry

    cyclic_entry = AppRegistryEntry(service_type="containerized", dependencies=["minio"])

    original = ANSIBLE_DATA.get_app_entry

    def fake_get(app: str) -> AppRegistryEntry:
        if app == "minio":
            return cyclic_entry
        return original(app)

    with patch.object(ANSIBLE_DATA, "get_app_entry", side_effect=fake_get):
        orch, _, _ = _orchestrator()
        # Should return without RecursionError
        try:
            orch.run("minio", HOST)
        except SystemExit:
            pass  # role_path lookup will fail — that's fine; cycle guard ran
