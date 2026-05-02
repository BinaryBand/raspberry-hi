"""Contract checks for ansible role caddy."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_caddy_role_asserts_required_host_vars_before_install() -> None:
    """Role should assert caddy_acme_email and caddy_routes are configured."""
    content = (ROOT / "ansible/roles/caddy/tasks/main.yml").read_text(encoding="utf-8")

    assert "Assert caddy_acme_email is set" in content
    assert "Assert caddy_routes is non-empty" in content


def test_caddy_role_rejects_duplicate_routes() -> None:
    """Role should assert no duplicate host, external, or internal values in caddy_routes."""
    content = (ROOT / "ansible/roles/caddy/tasks/main.yml").read_text(encoding="utf-8")

    assert "Assert caddy_routes has no duplicate host labels" in content
    assert "Assert caddy_routes has no duplicate external addresses" in content
    assert "Assert caddy_routes has no duplicate internal addresses" in content


def test_caddy_role_installs_package_and_deploys_caddyfile() -> None:
    """Role should install the caddy package and template the Caddyfile."""
    content = (ROOT / "ansible/roles/caddy/tasks/main.yml").read_text(encoding="utf-8")

    assert "Install caddy" in content
    assert "Install Caddyfile" in content
    assert "Caddyfile.j2" in content
