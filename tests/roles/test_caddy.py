"""Contract checks for ansible role caddy."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_caddy_role_asserts_required_host_vars_before_install() -> None:
    """Role should assert caddy_acme_email and caddy_server_name are set."""
    content = (ROOT / "ansible/roles/caddy/tasks/main.yml").read_text(encoding="utf-8")

    assert "Assert caddy_acme_email is set" in content
    assert "Assert caddy_server_name is set" in content


def test_caddy_role_installs_package_and_deploys_caddyfile() -> None:
    """Role should install the caddy package and template the Caddyfile."""
    content = (ROOT / "ansible/roles/caddy/tasks/main.yml").read_text(encoding="utf-8")

    assert "Install caddy" in content
    assert "Install Caddyfile" in content
    assert "Caddyfile.j2" in content
