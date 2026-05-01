"""Unit tests for preflight CLI entrypoint."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from linux_hi.cli import preflight
from linux_hi.services.preflight import PreflightError


def _patch_preflight_runtime(
    monkeypatch: pytest.MonkeyPatch,
    *,
    require_inventory_host: Callable[[str], str],
    run: Callable[[str, str], None],
) -> None:
    """Patch preflight dependencies with custom host validation and run behavior."""

    class _Store:
        def require_inventory_host(self, host: str) -> str:
            return require_inventory_host(host)

    class _Orchestrator:
        def __init__(self, **_kwargs: object) -> None:
            """Accept injected ports in test double constructor."""

        def run(self, app: str, hostname: str) -> None:
            run(app, hostname)

    monkeypatch.setenv("HOST", "rpi")
    monkeypatch.setattr(preflight, "ANSIBLE_DATA", _Store())
    monkeypatch.setattr(preflight, "_build_registry", lambda: object())
    monkeypatch.setattr(preflight, "AnsibleHostVarsStore", lambda: object())
    monkeypatch.setattr(preflight, "AnsibleVaultStore", lambda: object())
    monkeypatch.setattr(preflight, "PreflightOrchestrator", _Orchestrator)


def test_main_requires_app_argument() -> None:
    """Main should exit with usage text when app argument is missing."""
    with pytest.raises(SystemExit) as exc:
        preflight.main([])

    assert "Usage: preflight.py <app>" in str(exc.value)


def test_main_requires_host_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Main should exit when HOST environment variable is not set."""
    monkeypatch.delenv("HOST", raising=False)

    with pytest.raises(SystemExit) as exc:
        preflight.main(["postgres"])

    assert "HOST is required" in str(exc.value)


def test_main_runs_orchestrator_with_validated_host(monkeypatch: pytest.MonkeyPatch) -> None:
    """Main should validate host alias and run orchestrator for the target app."""
    calls: list[tuple[str, str]] = []

    def _require(host: str) -> str:
        calls.append(("require", host))
        return "validated-host"

    def _run(app: str, hostname: str) -> None:
        calls.append((app, hostname))

    _patch_preflight_runtime(
        monkeypatch,
        require_inventory_host=_require,
        run=_run,
    )

    preflight.main(["synapse"])

    assert calls == [("require", "rpi"), ("synapse", "validated-host")]


def test_main_exits_on_preflight_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Main should convert preflight orchestration errors into CLI failure output."""

    def _raise(_app: str, _hostname: str) -> None:
        raise PreflightError("bad settings")

    _patch_preflight_runtime(
        monkeypatch,
        require_inventory_host=lambda host: host,
        run=_raise,
    )

    with pytest.raises(SystemExit) as exc:
        preflight.main(["synapse"])

    assert "[FAIL]" in str(exc.value)
    assert "bad settings" in str(exc.value)
