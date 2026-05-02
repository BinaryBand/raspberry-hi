"""Contract checks for ansible role podman."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_podman_role_has_manager_branches_for_supported_distros() -> None:
    """Role should include package-manager specific task files."""
    content = (ROOT / "ansible/roles/podman/tasks/main.yml").read_text(encoding="utf-8")

    for mgr in ("apt", "dnf", "apk", "pacman", "zypper"):
        assert f"Install Podman ({mgr})" in content
        assert f"pkg_{mgr}.yml" in content


def test_podman_defaults_define_supported_managers() -> None:
    """Defaults must list package managers supported during base bootstrap."""
    content = (ROOT / "ansible/roles/podman/defaults/main.yml").read_text(encoding="utf-8")

    assert "podman_supported_managers:" in content
    for mgr in ("apt", "dnf", "apk", "pacman", "zypper"):
        assert f"- {mgr}" in content
