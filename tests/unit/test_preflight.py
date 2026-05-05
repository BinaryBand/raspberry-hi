"""Tests for registry-driven preflight metadata and orchestration behaviour."""

from __future__ import annotations

from pathlib import Path

import pytest

from linux_hi.models import ANSIBLE_DATA
from linux_hi.models.ansible.registry import AppRegistryEntry, VaultSecretSpec
from linux_hi.services.preflight import (
    PreflightError,
    PreflightOrchestrator,
    _host_has_forwards,
    load_preflight_spec,
)
from tests.support.preflight_fakes import FakeHostVarsStore, FakePromptRegistry, FakeVaultStore

# ---------------------------------------------------------------------------
# Registry structure tests
# ---------------------------------------------------------------------------


def test_ansible_dir_exists() -> None:
    """The helper should point at the checked-in Ansible directory."""
    assert ANSIBLE_DATA.ansible_dir.exists()
    assert (ANSIBLE_DATA.ansible_dir / "registry.yml").exists()


def test_registered_apps_have_role_directories() -> None:
    """Each registered app must resolve to a role directory under ansible/roles."""
    for app in ANSIBLE_DATA.all_apps():
        assert ANSIBLE_DATA.role_path(app).exists()


def test_registry_entries_expose_preflight_fields() -> None:
    """Each registry entry should declare preflight vars and vault secret metadata."""
    for app in ANSIBLE_DATA.all_apps():
        entry = ANSIBLE_DATA.get_app_entry(app)
        assert isinstance(entry.preflight_vars, dict)
        assert isinstance(entry.vault_secrets, list)
        for spec in entry.preflight_vars.values():
            assert spec.type in {"text", "password", "rclone_remote", "path"}


# ---------------------------------------------------------------------------
# VaultSecretSpec.prompt_type
# ---------------------------------------------------------------------------


def test_vault_secret_prompt_type_hidden() -> None:
    """A hidden secret resolves to the 'password' prompt type."""
    hidden = next(
        secret
        for app in ANSIBLE_DATA.all_apps()
        for secret in ANSIBLE_DATA.get_app_entry(app).vault_secrets
        if secret.hidden
    )
    assert hidden.prompt_type == "password"


def test_vault_secret_prompt_type_visible() -> None:
    """A non-hidden secret resolves to the 'text' prompt type."""
    visible = next(
        secret
        for app in ANSIBLE_DATA.all_apps()
        for secret in ANSIBLE_DATA.get_app_entry(app).vault_secrets
        if not secret.hidden
    )
    assert visible.prompt_type == "text"


# ---------------------------------------------------------------------------
# Orchestrator behavioural tests
# ---------------------------------------------------------------------------

HOST = "rpi"


def _dependency_closure(root_app: str) -> list[str]:
    closure: list[str] = []
    seen: set[str] = set()

    def _visit(app: str) -> None:
        if app in seen:
            return
        seen.add(app)
        closure.append(app)
        for dep in ANSIBLE_DATA.get_app_entry(app).dependencies:
            _visit(dep)

    _visit(root_app)
    return closure


def _find_app_with_vars_and_secrets() -> str:
    for app in ANSIBLE_DATA.all_apps():
        role_path = ANSIBLE_DATA.role_path(app)
        vars_spec, secrets_spec = load_preflight_spec(app, role_path)
        if vars_spec and secrets_spec:
            return app
    pytest.skip("No app has both preflight vars and vault secrets")


def _find_app_with_generate_secret() -> tuple[str, list[VaultSecretSpec]]:
    for app in ANSIBLE_DATA.all_apps():
        role_path = ANSIBLE_DATA.role_path(app)
        _, secrets_spec = load_preflight_spec(app, role_path)
        generated = [spec for spec in secrets_spec if spec.generate]
        if generated:
            return app, generated
    pytest.skip("No app has generate=True secrets")


def _preflight_state_for(
    app: str, *, leave_generated_for_target: bool = False
) -> tuple[dict[str, object], dict[str, object], dict[str, str]]:
    host_vars: dict[str, object] = {}
    vault_data: dict[str, object] = {}
    prompt_responses = {
        "text": "/srv/test-path",
        "path": "/srv/test-path",
        "rclone_remote": "remote:test-path",
        "password": "test-secret",
    }

    for current in _dependency_closure(app):
        role_path = ANSIBLE_DATA.role_path(current)
        vars_spec, secrets_spec = load_preflight_spec(current, role_path)
        for var_name in vars_spec:
            host_vars[var_name] = "/srv/test-path"
        for secret in secrets_spec:
            if leave_generated_for_target and current == app and secret.generate:
                continue
            vault_data[secret.key] = "preset-secret"

    return host_vars, vault_data, prompt_responses


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
    app = _find_app_with_vars_and_secrets()
    host_vars, vault_data, _ = _preflight_state_for(app)
    orch, hv, _ = _orchestrator(host_vars=host_vars, vault=vault_data)
    orch.run(app, HOST)
    assert HOST not in hv.written


def test_missing_vars_are_prompted_and_written() -> None:
    """A missing host var triggers a prompt and is persisted."""
    app = _find_app_with_vars_and_secrets()
    role_path = ANSIBLE_DATA.role_path(app)
    vars_spec, _ = load_preflight_spec(app, role_path)
    target_var = next(iter(vars_spec))
    var_type = vars_spec[target_var].type

    host_vars, vault_data, prompt_responses = _preflight_state_for(app)
    del host_vars[target_var]
    expected = prompt_responses[var_type]

    orch, hv, _ = _orchestrator(
        responses=prompt_responses,
        host_vars=host_vars,
        vault=vault_data,
    )
    orch.run(app, HOST)
    assert hv.written.get(HOST, {}).get(target_var) == expected


def test_already_set_secrets_are_skipped() -> None:
    """Secrets already in the vault are not prompted and the vault is not rewritten."""
    app = _find_app_with_vars_and_secrets()
    host_vars, vault_data, _ = _preflight_state_for(app)
    orch, _, v = _orchestrator(host_vars=host_vars, vault=vault_data)
    orch.run(app, HOST)
    assert v.written == []


def test_generate_flag_auto_fills_empty_secret() -> None:
    """An empty response for a generate=True secret produces a hex token."""
    app, generate_secrets = _find_app_with_generate_secret()
    host_vars, vault_data, _ = _preflight_state_for(app, leave_generated_for_target=True)

    orch, _, v = _orchestrator(host_vars=host_vars, vault=vault_data, responses={})
    orch.run(app, HOST)

    assert v.written
    for secret in generate_secrets:
        written_val = v.written[-1].get(secret.key, "")
        assert isinstance(written_val, str)
        assert len(written_val) == 64  # token_hex(32) -> 64 hex chars


def test_dependency_reads_once_per_closure_app() -> None:
    """Dependency traversal should visit each app in the closure only once."""
    candidate = next(
        (app for app in ANSIBLE_DATA.all_apps() if ANSIBLE_DATA.get_app_entry(app).dependencies),
        None,
    )
    if candidate is None:
        pytest.skip("No app declares dependencies")

    reads = 0

    class TrackingStore(FakeHostVarsStore):
        def read(self, hostname: str) -> dict[str, object]:
            nonlocal reads
            reads += 1
            return super().read(hostname)

    all_vars, all_secrets, _ = _preflight_state_for(candidate)
    hv = TrackingStore(initial={HOST: all_vars})
    v = FakeVaultStore(initial=all_secrets)
    orch = PreflightOrchestrator(registry=FakePromptRegistry({}), hv=hv, vault=v)
    orch.run(candidate, HOST)

    assert reads == len(_dependency_closure(candidate))


def test_cycle_detection_prevents_infinite_loop() -> None:
    """Artificially cyclic dependency entries do not cause infinite recursion."""
    from unittest.mock import patch

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
        except PreflightError:
            pass  # role_path lookup will fail - that's fine; cycle guard ran


def test_caddy_preflight_injected_when_host_has_forwards(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Caddy preflight should run automatically when forwards.yml has an entry for the host."""
    from linux_hi.services import preflight as pf_module

    visited: list[str] = []
    original_run_for = PreflightOrchestrator._run_for

    def _tracking_run_for(self: PreflightOrchestrator, app: str, hostname: str, seen: set) -> None:
        visited.append(app)
        original_run_for(self, app, hostname, seen)

    monkeypatch.setattr(pf_module, "_host_has_forwards", lambda _hostname: True)
    monkeypatch.setattr(PreflightOrchestrator, "_run_for", _tracking_run_for)

    orch, _, _ = _orchestrator()
    try:
        orch.run("minio", HOST)
    except (PreflightError, KeyError):
        pass

    assert "caddy" in visited


def test_host_has_forwards_returns_false_when_file_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_host_has_forwards should return False when forwards.yml does not exist."""
    monkeypatch.setattr(ANSIBLE_DATA, "ansible_dir", tmp_path / "ansible")
    assert not _host_has_forwards("rpi")


def test_host_has_forwards_returns_true_for_matching_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_host_has_forwards should return True when the hostname appears in reverse_proxies."""
    ansible_dir = tmp_path / "ansible" / "group_vars" / "all"
    ansible_dir.mkdir(parents=True)
    (ansible_dir / "forwards.yml").write_text(
        "reverse_proxies:\n  - service: minio\n    host: rpi\n    domain: minio.example.com\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(ANSIBLE_DATA, "ansible_dir", tmp_path / "ansible")
    assert _host_has_forwards("rpi")
    assert not _host_has_forwards("other-host")
