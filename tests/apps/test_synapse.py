"""App-specific contract tests for Synapse."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_synapse_admin_seeding_is_idempotent() -> None:
    """Admin seeding must check for an existing user before attempting registration."""
    setup_admin = _read_text("ansible/roles/apps/synapse/tasks/setup_admin.yml")

    assert "Check whether Synapse admin user exists" in setup_admin
    assert "Register Synapse admin user" in setup_admin
    assert "_synapse_admin_check.stdout" in setup_admin


def test_synapse_admin_tasks_suppress_secrets_in_logs() -> None:
    """Tasks that handle admin credentials must set no_log: true."""
    setup_admin = _read_text("ansible/roles/apps/synapse/tasks/setup_admin.yml")

    assert setup_admin.count("no_log: true") >= 2


def test_synapse_main_tasks_include_admin_seeding() -> None:
    """Synapse main tasks must include the admin seeding step after service registration."""
    tasks = _read_text("ansible/roles/apps/synapse/tasks/main.yml")

    assert "setup_admin.yml" in tasks
