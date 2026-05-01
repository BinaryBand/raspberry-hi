"""E2E connectivity and device discovery tests — require a live Pi.

Run with: make test-e2e
"""

import os
from pathlib import Path

import pytest

from linux_hi.adapters.connection_types import RemoteConnection
from linux_hi.models import ANSIBLE_DATA
from linux_hi.models.ansible.role_vars import role_required_vars
from linux_hi.services.vault import VAULT_PASSWORD_FILE, decrypt_vault
from linux_hi.storage.devices import get_block_devices, get_real_mounts
from linux_hi.utils.exec import run_resolved


@pytest.mark.e2e
def test_root_mount_exists(live_conn: RemoteConnection) -> None:
    """Verify root mount is found in real system mounts."""
    mounts = get_real_mounts(live_conn)
    assert any(m.target == "/" for m in mounts), "No root mount found"


@pytest.mark.e2e
def test_real_mounts_have_source_and_fstype(live_conn: RemoteConnection) -> None:
    """Verify real mounts have source and fstype attributes."""
    mounts = get_real_mounts(live_conn)
    assert mounts, "findmnt returned no mounts"
    for m in mounts:
        assert m.source is not None
        assert m.fstype is not None


@pytest.mark.e2e
def test_block_devices_discoverable(live_conn: RemoteConnection) -> None:
    """Verify block devices are discoverable on the live system."""
    devices = get_block_devices(live_conn)
    assert devices, "lsblk returned no devices"
    assert all(d.name for d in devices)


@pytest.mark.e2e
def test_root_device_classified_as_system(live_conn: RemoteConnection) -> None:
    """Verify the disk hosting the root filesystem is classified as a system device."""
    from linux_hi.storage.devices import is_system_device

    devices = get_block_devices(live_conn)
    # Find whichever disk contains a partition mounted at /
    root_disks = [
        d
        for d in devices
        if d.type == "disk" and any(c.mountpoint == "/" for c in (d.children or []))
    ]
    assert root_disks, "No disk found hosting the root partition"
    assert all(is_system_device(d) for d in root_disks)


@pytest.mark.e2e
def test_inventory_host_wiring_sanity(selected_host: str) -> None:
    """Verify selected host is in inventory with usable connection details."""
    assert ANSIBLE_DATA.require_inventory_host(selected_host) == selected_host

    host_vars = ANSIBLE_DATA.host_vars(selected_host)
    assert host_vars.ansible_host, f"Host '{selected_host}' is missing ansible_host"
    assert host_vars.ansible_user, f"Host '{selected_host}' is missing ansible_user"
    assert (host_vars.ansible_port or 22) > 0

    if host_vars.ansible_ssh_private_key_file:
        key_path = Path(host_vars.ansible_ssh_private_key_file)
        if not key_path.is_absolute():
            key_path = ANSIBLE_DATA.root / key_path
        assert key_path.exists(), f"SSH key path does not exist for '{selected_host}': {key_path}"


@pytest.mark.e2e
def test_vault_accessibility_for_selected_host(selected_host: str) -> None:
    """Verify vault decrypt works and selected host has a become password."""
    assert VAULT_PASSWORD_FILE.exists(), f"Missing vault password file: {VAULT_PASSWORD_FILE}"

    secrets = decrypt_vault()
    become_passwords = secrets.become_passwords or {}
    assert selected_host in become_passwords, (
        f"Vault is missing become password for host '{selected_host}'"
    )
    assert become_passwords[selected_host], (
        f"Vault become password for host '{selected_host}' is empty"
    )


@pytest.mark.e2e
def test_ansible_site_syntax_probe(selected_host: str) -> None:
    """Verify Ansible setup playbook parses for the selected host."""
    result = run_resolved(
        [
            "ansible-playbook",
            "--syntax-check",
            str(ANSIBLE_DATA.ansible_dir / "playbooks" / "setup.yml"),
            "-i",
            str(ANSIBLE_DATA.inventory_file),
            "--vault-password-file",
            str(VAULT_PASSWORD_FILE),
            "--limit",
            selected_host,
        ],
        env={**os.environ, "ANSIBLE_CONFIG": str(ANSIBLE_DATA.ansible_dir / "ansible.cfg")},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Ansible syntax check failed for host '{selected_host}':\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


@pytest.mark.e2e
def test_service_adapter_contract_smoke() -> None:
    """Verify service_adapter role shape and required-vars contract."""
    role_path = ANSIBLE_DATA.role_path("service_adapter")
    assert (role_path / "tasks" / "start.yml").exists()
    assert (role_path / "tasks" / "stop.yml").exists()
    assert (role_path / "tasks" / "restart.yml").exists()

    required_vars = role_required_vars(role_path)
    assert not required_vars, (
        "service_adapter should not require host-specific defaults, "
        f"but missing values were found: {required_vars}"
    )


@pytest.mark.e2e
def test_app_registry_smoke_for_live_host() -> None:
    """Verify registry metadata aligns with role structure for containerized apps."""
    containerized_apps = ANSIBLE_DATA.containerized_apps()
    assert containerized_apps, "No containerized apps found in registry"

    for app in containerized_apps:
        entry = ANSIBLE_DATA.get_app_entry(app)
        role_path = ANSIBLE_DATA.role_path(app)

        assert entry.service_type == "containerized", (
            f"Registry entry for '{app}' is not containerized"
        )
        assert entry.service_name, f"Containerized app '{app}' is missing service_name in registry"
        assert (role_path / "tasks" / "main.yml").exists(), (
            f"Role tasks/main.yml is missing for app '{app}'"
        )
