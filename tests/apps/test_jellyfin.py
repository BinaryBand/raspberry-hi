"""App-specific contract tests for Jellyfin."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_jellyfin_role_wires_read_only_media_mount() -> None:
    """Jellyfin should mount host media as read-only both in rclone and the container."""
    unit = _read_text("ansible/roles/apps/jellyfin/templates/jellyfin-media-library.service.j2")
    tasks = _read_text("ansible/roles/apps/jellyfin/tasks/main.yml")

    assert "--read-only" in unit
    assert "jellyfin_media_mount_path }}:/media:ro" in tasks


def test_jellyfin_container_depends_on_media_mount_unit() -> None:
    """Jellyfin container quadlet should want and start after media mount service."""
    tasks = _read_text("ansible/roles/apps/jellyfin/tasks/main.yml")

    assert "service_adapter_unit_after:" in tasks
    assert "service_adapter_unit_wants:" in tasks
    assert "jellyfin-media-library.service" in tasks
