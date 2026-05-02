"""Contract checks for ansible role auto-updates."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_auto_updates_role_has_manager_branches_for_supported_distros() -> None:
    """Role should gate on pkg_mgr and include one task file per supported manager."""
    content = (ROOT / "ansible/roles/auto-updates/tasks/main.yml").read_text(encoding="utf-8")

    for mgr in ("apt", "dnf", "zypper", "apk", "pacman"):
        assert f"Configure auto-updates ({mgr})" in content
        assert f"pkg_{mgr}.yml" in content


def test_auto_updates_defaults_define_supported_managers() -> None:
    """Defaults must declare supported package managers for blank-host provisioning."""
    content = (ROOT / "ansible/roles/auto-updates/defaults/main.yml").read_text(encoding="utf-8")

    assert "auto_updates_supported_managers:" in content
    for mgr in ("apt", "dnf", "zypper", "apk", "pacman"):
        assert f"- {mgr}" in content
