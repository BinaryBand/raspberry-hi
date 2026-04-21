"""Tests for registry-driven preflight metadata."""

from __future__ import annotations

from models import ANSIBLE_DATA


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
