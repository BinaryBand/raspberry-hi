#!/usr/bin/env python3
"""
Pre-flight for 'make site': ensures MinIO data will land on external storage.
If minio_data_path isn't on a non-root mount, guides the user through options
and writes the chosen configuration back to host_vars before Ansible runs.
"""

import json
import os
import sys
from pathlib import Path

import questionary
import yaml
from rich.console import Console

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS_DIR))

from exec_utils import run_resolved  # noqa: E402
from models import HostVars  # noqa: E402

ANSIBLE_DIR = ROOT / "ansible"
MINIO_DEFAULTS_FILE = ANSIBLE_DIR / "roles" / "minio" / "defaults" / "main.yml"
HOST_VARS_DIR = ANSIBLE_DIR / "inventory" / "host_vars"
MOUNT_PLAYBOOK = ANSIBLE_DIR / "mount_storage.yml"

HOST = "rpi"

console = Console()


# ---------------------------------------------------------------------------
# Ansible inventory helpers
# ---------------------------------------------------------------------------


def _inventory_host_vars() -> HostVars:
    result = run_resolved(
        ["ansible-inventory", "--host", HOST],
        capture_output=True,
        text=True,
        cwd=str(ANSIBLE_DIR),
    )
    if result.returncode != 0:
        raise RuntimeError(f"ansible-inventory failed: {result.stderr.strip()}")
    return HostVars.model_validate(json.loads(result.stdout))


def _read_minio_defaults() -> dict:
    with open(MINIO_DEFAULTS_FILE) as f:
        return yaml.safe_load(f) or {}


def _read_host_vars_file() -> dict:
    path = HOST_VARS_DIR / f"{HOST}.yml"
    return yaml.safe_load(path.read_text()) or {} if path.exists() else {}


def _write_host_vars_file(data: dict) -> None:
    path = HOST_VARS_DIR / f"{HOST}.yml"
    with open(path, "w") as f:
        f.write("---\n")
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def _update_host_vars(**kwargs) -> None:
    data = _read_host_vars_file()
    data.update(kwargs)
    _write_host_vars_file(data)


# ---------------------------------------------------------------------------
# Remote helpers
# ---------------------------------------------------------------------------


def _make_connection(hvars: HostVars):
    from fabric import Connection

    connect_kwargs: dict = {}
    if hvars.ansible_ssh_private_key_file:
        key_path = Path(hvars.ansible_ssh_private_key_file)
        if not key_path.is_absolute():
            key_path = ROOT / key_path
        connect_kwargs["key_filename"] = str(key_path)
    return Connection(host=hvars.ansible_host, user=hvars.ansible_user, connect_kwargs=connect_kwargs)


def _get_real_mounts(conn) -> list[dict]:
    """Return all real (non-virtual) mount points on the Pi as a list of dicts."""
    result = conn.run("findmnt -J -o TARGET,SOURCE,FSTYPE,SIZE --real 2>/dev/null", hide=True, warn=True)
    if not result.ok or not result.stdout.strip():
        return []
    return json.loads(result.stdout).get("filesystems", [])


def _mount_covering(mounts: list[dict], path: str) -> str:
    """Return the most-specific mount point that covers *path* (no SSH needed)."""
    covering = "/"
    for fs in mounts:
        target = fs.get("target", "")
        normalised = target.rstrip("/")
        if path == normalised or path.startswith(normalised + "/"):
            if len(target) > len(covering):
                covering = target
    return covering


def _external_mounts(mounts: list[dict]) -> list[dict]:
    """Filter out the root fs and known virtual/system mount prefixes."""
    skip_exact = {"/", "/boot", "/boot/firmware"}
    skip_prefixes = ("/sys", "/proc", "/dev", "/run")
    return [
        fs
        for fs in mounts
        if (t := fs.get("target", ""))
        and t not in skip_exact
        and not any(t.startswith(p) for p in skip_prefixes)
    ]


# ---------------------------------------------------------------------------
# Interactive flows
# ---------------------------------------------------------------------------


def _flow_mount_new_device(conn) -> str | None:
    """List unmounted external block devices, mount the chosen one, return its mount point."""
    from models import BlockDevice
    from pick_storage import display_devices, get_external_devices

    result = conn.run("lsblk -J -o NAME,SIZE,TYPE,MOUNTPOINT,LABEL,FSTYPE", hide=True)
    raw = json.loads(result.stdout)["blockdevices"]
    devices = get_external_devices([BlockDevice.model_validate(d) for d in raw])

    if not devices:
        console.print("[yellow]No external storage devices found on the Pi.[/yellow]")
        return None

    display_devices(devices)

    selected = questionary.select(
        "Select a device to mount:",
        choices=[
            questionary.Choice(title=f"/dev/{d.name}  {d.label or ''}  ({d.size or '?'})", value=d)
            for d in devices
        ],
    ).ask()
    if not selected:
        return None

    label = questionary.text(
        "Mount point label (will mount at /mnt/<label>):",
        default=selected.label or selected.name,
    ).ask()
    if not label:
        return None

    console.print(f"\n[bold green]Mounting /dev/{selected.name} at /mnt/{label}...[/bold green]")
    run_resolved(
        ["ansible-playbook", str(MOUNT_PLAYBOOK), "-e", f"device=/dev/{selected.name}", "-e", f"label={label}"],
        cwd=str(ROOT),
        env={**os.environ, "ANSIBLE_CONFIG": str(ANSIBLE_DIR / "ansible.cfg")},
        check=True,
    )
    return f"/mnt/{label}"


def _flow_use_existing_mount(mounts: list[dict]) -> str | None:
    """Let the user pick from already-mounted external filesystems."""
    external = _external_mounts(mounts)
    if not external:
        console.print("[yellow]No external mounts found on the Pi.[/yellow]")
        return None

    return questionary.select(
        "Select the mount point to use for MinIO data:",
        choices=[
            questionary.Choice(
                title=f"{fs['target']}  ({fs.get('source', '?')}, {fs.get('fstype', '?')}, {fs.get('size', '?')})",
                value=fs["target"],
            )
            for fs in external
        ],
    ).ask()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    defaults = _read_minio_defaults()
    host_vars = _read_host_vars_file()

    minio_data_path: str = host_vars.get("minio_data_path", defaults.get("minio_data_path", "/srv/minio/data"))
    require_external: bool = host_vars.get(
        "minio_require_external_mount",
        defaults.get("minio_require_external_mount", True),
    )

    if not require_external:
        console.print("[dim]MinIO external-mount check skipped (minio_require_external_mount: false).[/dim]")
        return

    console.print("[bold]Checking MinIO storage configuration...[/bold]")

    hvars = _inventory_host_vars()
    conn = _make_connection(hvars)
    mounts = _get_real_mounts(conn)
    covering = _mount_covering(mounts, minio_data_path)

    if covering != "/":
        console.print(
            f"[green]MinIO data path [bold]{minio_data_path}[/bold] "
            f"is on external mount [bold]{covering}[/bold].[/green]"
        )
        return

    # Not on an external mount — guide the user
    console.print(
        f"\n[yellow]MinIO data path [bold]{minio_data_path}[/bold] is on the root filesystem.[/yellow]\n"
        "Storing MinIO data on an external drive protects against root-fs wear\n"
        "and keeps data separate from the OS.\n"
    )

    action = questionary.select(
        "How would you like to proceed?",
        choices=[
            questionary.Choice("Mount external storage now", value="mount"),
            questionary.Choice("Use a drive that's already mounted", value="existing"),
            questionary.Choice("Use root filesystem (not recommended)", value="skip"),
            questionary.Choice("Abort", value="abort"),
        ],
    ).ask()

    if action is None or action == "abort":
        sys.exit(1)

    if action == "skip":
        _update_host_vars(minio_require_external_mount=False)
        console.print("[dim]Wrote minio_require_external_mount: false to host_vars. Continuing...[/dim]")
        return

    base = _flow_mount_new_device(conn) if action == "mount" else _flow_use_existing_mount(mounts)

    if not base:
        console.print("[red]No mount point selected. Aborting.[/red]")
        sys.exit(1)

    subdir = questionary.text(
        "Subdirectory for MinIO data within the mount:",
        default="minio/data",
    ).ask()
    if not subdir:
        sys.exit(1)

    new_path = f"{base.rstrip('/')}/{subdir.strip('/')}"
    _update_host_vars(minio_data_path=new_path)
    console.print(f"\n[bold green]Set minio_data_path: {new_path} in host_vars.[/bold green]")


if __name__ == "__main__":
    main()
