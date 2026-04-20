"""Tests for registry-driven preflight metadata."""

from __future__ import annotations

from scripts.utils.ansible_utils import ANSIBLE_DIR, all_apps, get_app_entry


def test_ansible_dir_exists() -> None:
    """The helper should point at the checked-in Ansible directory."""
    assert ANSIBLE_DIR.exists()
    assert (ANSIBLE_DIR / "registry.yml").exists()


def test_registered_apps_have_role_directories() -> None:
    """Each registered app must resolve to a role directory under ansible/apps."""
    for app in all_apps():
        assert (ANSIBLE_DIR / "apps" / app).exists()


def test_registry_entries_expose_preflight_fields() -> None:
    """Each registry entry should declare preflight vars and vault secret metadata."""
    for app in all_apps():
        entry = get_app_entry(app)
        assert isinstance(entry.preflight_vars, dict)
        assert isinstance(entry.vault_secrets, list)
