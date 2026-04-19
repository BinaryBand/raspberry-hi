"""Contract tests for Ansible app wiring that has broken before."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
ANSIBLE_DIR = ROOT / "ansible"


def _read_text(relative_path: str) -> str:
    """Return the text content of a repository file."""
    return (ROOT / relative_path).read_text()


def _read_yaml(relative_path: str) -> Any:
    """Return the YAML-decoded content of a repository file."""
    return yaml.safe_load((ROOT / relative_path).read_text())


class TestBaikalContracts:
    """Guardrails for Baikal's declarative PostgreSQL wiring."""

    def test_baikal_uses_host_access_name_without_inline_port(self) -> None:
        """Baikal must pass only the host-access name to pgsql_host."""
        defaults = _read_yaml("ansible/apps/baikal/defaults/main.yml")

        assert isinstance(defaults, dict)
        assert defaults["baikal_db_host"] == "{{ postgres_host_access_name }}"

    def test_baikal_uses_default_container_network(self) -> None:
        """Baikal should not depend on a custom Podman bridge network."""
        template = _read_text("ansible/apps/baikal/templates/baikal.container.j2")

        assert "Network=" not in template

    def test_baikal_marks_installation_complete(self) -> None:
        """Declarative provisioning must disable the installer route afterwards."""
        tasks = _read_text("ansible/apps/baikal/tasks/main.yml")

        assert "Disable Baikal install tool after declarative provisioning" in tasks
        assert "INSTALL_DISABLED" in tasks


class TestCleanupContracts:
    """Guardrails for the cleanup playbook and per-app teardown tasks."""

    def test_cleanup_playbook_requires_cleanup_app(self) -> None:
        """cleanup.yml must assert that cleanup_app is defined before doing anything."""
        playbook = _read_text("ansible/cleanup.yml")

        assert "cleanup_app is defined" in playbook

    def test_cleanup_playbook_has_confirmation_prompt(self) -> None:
        """cleanup.yml must pause for confirmation before destructive steps."""
        playbook = _read_text("ansible/cleanup.yml")

        assert "ansible.builtin.pause" in playbook
        assert "PERMANENTLY DELETE" in playbook

    def test_postgres_cleanup_aborts_if_baikal_still_deployed(self) -> None:
        """Postgres cleanup must refuse to run if the baikal quadlet still exists."""
        tasks = _read_text("ansible/apps/postgres/tasks/cleanup.yml")

        assert "baikal.container" in tasks
        assert "ansible.builtin.fail" in tasks

    def test_baikal_cleanup_drops_database(self) -> None:
        """Baikal cleanup must drop the baikal database from the postgres container."""
        tasks = _read_text("ansible/apps/baikal/tasks/cleanup.yml")

        assert "dropdb" in tasks
        assert "postgres_service_name" in tasks


class TestAnsibleStructureContracts:
    """Guardrails for Ansible structural patterns that have caused runtime failures."""

    def test_no_app_meta_dependencies(self) -> None:
        """App meta files must declare empty dependencies — ordering belongs in site.yml tags.

        Non-empty meta dependencies cause roles to run multiple times under tag-based
        invocation, which can time out on repeated privilege escalation.
        """
        for meta_file in sorted((ANSIBLE_DIR / "apps").glob("*/meta/main.yml")):
            data = _read_yaml(f"ansible/apps/{meta_file.parent.parent.name}/meta/main.yml")
            assert isinstance(data, dict)
            assert "dependencies" not in data or data["dependencies"] == [], (
                f"{meta_file.parent.parent.name}/meta/main.yml has non-empty dependencies; "
                "declare ordering via site.yml tags instead"
            )

    def test_cleanup_does_not_use_include_vars(self) -> None:
        """cleanup.yml must not use include_vars to load role defaults.

        include_vars has higher precedence than host_vars, so loading a defaults file
        that contains null-sentinel required vars (e.g. postgres_data_path: ~) silently
        overrides the host_vars values, causing file-removal tasks to no-op.
        """
        playbook = _read_text("ansible/cleanup.yml")

        assert "include_vars:" not in playbook

    def test_all_app_main_tasks_call_service_adapter(self) -> None:
        """Every app tasks/main.yml must register with service_adapter.

        Without service_adapter registration the service silently fails to start on boot
        regardless of whether the container and quadlet are correctly deployed.
        """
        for tasks_file in sorted((ANSIBLE_DIR / "apps").glob("*/tasks/main.yml")):
            app_name = tasks_file.parent.parent.name
            content = _read_text(f"ansible/apps/{app_name}/tasks/main.yml")
            assert "name: service_adapter" in content, (
                f"{app_name}/tasks/main.yml must register with service_adapter"
            )

    def test_all_app_cleanup_tasks_call_service_adapter_teardown(self) -> None:
        """Every app tasks/cleanup.yml must call service_adapter teardown.

        Skipping teardown leaves orphaned systemd units or cron entries on the host
        after cleanup, causing the service to restart on next boot despite being removed.
        """
        for cleanup_file in sorted((ANSIBLE_DIR / "apps").glob("*/tasks/cleanup.yml")):
            app_name = cleanup_file.parent.parent.name
            content = _read_text(f"ansible/apps/{app_name}/tasks/cleanup.yml")
            assert "tasks_from: teardown" in content, (
                f"{app_name}/tasks/cleanup.yml must call service_adapter with tasks_from: teardown"
            )

    def test_all_app_quadlets_have_network_ordering(self) -> None:
        """All Podman quadlet templates must include After=network.target.

        Without this ordering directive, containerised services may attempt to start
        before networking is available, causing silent connection failures at boot.
        """
        for quadlet in sorted((ANSIBLE_DIR / "apps").glob("*/templates/*.container.j2")):
            app_name = quadlet.parent.parent.name
            content = _read_text(f"ansible/apps/{app_name}/templates/{quadlet.name}")
            assert "After=network.target" in content, (
                f"{app_name}/{quadlet.name} must have After=network.target"
            )

    def test_all_app_quadlets_have_install_section(self) -> None:
        """All Podman quadlet templates must include WantedBy=default.target.

        Without it the service does not autostart on boot after a host reboot.
        """
        for quadlet in sorted((ANSIBLE_DIR / "apps").glob("*/templates/*.container.j2")):
            app_name = quadlet.parent.parent.name
            content = _read_text(f"ansible/apps/{app_name}/templates/{quadlet.name}")
            assert "WantedBy=default.target" in content, (
                f"{app_name}/{quadlet.name} must have WantedBy=default.target"
            )

    def test_all_app_quadlets_have_restart_policy(self) -> None:
        """All Podman quadlet templates must include Restart=on-failure.

        Without a restart policy the container does not recover from crashes or
        host reboots, leaving the service silently down.
        """
        for quadlet in sorted((ANSIBLE_DIR / "apps").glob("*/templates/*.container.j2")):
            app_name = quadlet.parent.parent.name
            content = _read_text(f"ansible/apps/{app_name}/templates/{quadlet.name}")
            assert "Restart=on-failure" in content, (
                f"{app_name}/{quadlet.name} must have Restart=on-failure"
            )

    def test_all_0600_task_files_have_no_log(self) -> None:
        """Any app tasks/main.yml that deploys a mode 0600 file must also set no_log: true.

        mode 0600 files contain credentials. Without no_log the secret value is
        printed in plain text in Ansible's task output and any attached log sinks.
        """
        for tasks_file in sorted((ANSIBLE_DIR / "apps").glob("*/tasks/main.yml")):
            app_name = tasks_file.parent.parent.name
            content = _read_text(f"ansible/apps/{app_name}/tasks/main.yml")
            if 'mode: "0600"' in content:
                assert "no_log: true" in content, (
                    f"{app_name}/tasks/main.yml deploys a mode 0600 file but has no no_log: true"
                )


class TestPostgresContracts:
    """Guardrails for PostgreSQL network and auth wiring."""

    def test_postgres_hba_template_allows_host_access_network(self) -> None:
        """The managed HBA file must allow rootless host-access traffic."""
        template = _read_text("ansible/apps/postgres/templates/postgres.hba.conf.j2")

        assert "{{ ansible_facts['default_ipv4']['address'] }}/32" in template
        assert "169.254.0.0/16" in template

    def test_postgres_container_uses_managed_hba_file_without_custom_network(self) -> None:
        """PostgreSQL must mount HBA explicitly and avoid a custom bridge network."""
        template = _read_text("ansible/apps/postgres/templates/postgres.container.j2")

        assert "Exec=postgres -c hba_file={{ postgres_hba_container_path }}" in template
        assert (
            "Volume={{ postgres_hba_host_path }}:{{ postgres_hba_container_path }}:ro" in template
        )
        assert "Network=" not in template

    def test_postgres_role_renders_managed_hba_template_and_flushes_changes(self) -> None:
        """The PostgreSQL role must apply config changes before dependent roles run."""
        tasks = _read_text("ansible/apps/postgres/tasks/main.yml")

        assert "Install PostgreSQL pg_hba.conf" in tasks
        assert "src: postgres.hba.conf.j2" in tasks
        assert "Remove legacy PostgreSQL Podman network quadlet" in tasks
        assert "Apply pending PostgreSQL handler changes" in tasks
        assert "ansible.builtin.meta: flush_handlers" in tasks
        assert "lineinfile" not in tasks
