"""Contract checks for ansible role rclone."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_rclone_role_requires_vault_secret_before_config_deploy() -> None:
    """Role should assert rclone_config exists before writing config."""
    content = (ROOT / "ansible/roles/system/rclone/tasks/main.yml").read_text(encoding="utf-8")

    assert "Verify rclone_config secret is present" in content
    assert "rclone_config is defined" in content


def test_rclone_role_installs_binary_and_deploys_config() -> None:
    """Role should install package and template the config file."""
    content = (ROOT / "ansible/roles/system/rclone/tasks/main.yml").read_text(encoding="utf-8")

    assert "Install rclone" in content
    assert "Deploy rclone config" in content
    assert "rclone.conf.j2" in content
