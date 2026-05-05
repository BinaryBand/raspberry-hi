"""Contract checks for ansible role caddy."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_caddy_role_rejects_duplicate_routes() -> None:
    """Role should assert no duplicate host, external, or internal values in caddy_routes."""
    content = (ROOT / "ansible/roles/system/caddy/tasks/main.yml").read_text(encoding="utf-8")

    assert "Assert caddy_routes has no duplicate host labels" in content
    assert "Assert caddy_routes has no duplicate external addresses" in content
    assert "Assert caddy_routes has no duplicate internal addresses" in content


def test_caddy_role_installs_package_and_deploys_caddyfile() -> None:
    """Role should install the caddy package and template the Caddyfile."""
    content = (ROOT / "ansible/roles/system/caddy/tasks/main.yml").read_text(encoding="utf-8")

    assert "Install caddy" in content
    assert "Install Caddyfile" in content
    assert "Caddyfile.j2" in content


def test_caddy_role_builds_routes_from_forwards_yml() -> None:
    """Role should filter reverse_proxies by inventory_hostname and build caddy_routes."""
    content = (ROOT / "ansible/roles/system/caddy/tasks/main.yml").read_text(encoding="utf-8")

    assert "Collect forwards for this host from forwards.yml" in content
    assert "reverse_proxies" in content
    assert "inventory_hostname" in content
    assert "Build caddy_routes from host forwards and app port vars" in content
    assert "caddy_routes" in content


def test_caddy_role_skips_play_when_no_forwards_for_host() -> None:
    """Role should end the play early when no forwards are declared for the current host."""
    content = (ROOT / "ansible/roles/system/caddy/tasks/main.yml").read_text(encoding="utf-8")

    assert "Skip caddy" in content
    assert "ansible.builtin.meta: end_play" in content
    assert "_caddy_host_forwards | length == 0" in content
