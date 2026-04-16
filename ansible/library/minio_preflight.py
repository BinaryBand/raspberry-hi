#!/usr/bin/python
"""Ansible module that ensures MinIO data is placed on external storage.

This module is called by Ansible with ``delegate_to: localhost``.  It relies
on the project root and ``scripts/`` being on sys.path, which the Makefile
ensures via ``PYTHONPATH``.  The guard below makes the module self-healing
when invoked outside of ``make`` (e.g. direct ``ansible-playbook`` calls).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project utilities are importable regardless of how Ansible was invoked.
_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT), str(_ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import yaml  # noqa: E402
from ansible.module_utils.basic import AnsibleModule  # noqa: E402
from utils.ansible_utils import make_connection  # noqa: E402
from utils.storage_flows import flow_use_existing_mount, parse_path_hints  # noqa: E402
from utils.storage_utils import external_mounts, get_real_mounts, mount_covering  # noqa: E402

from models import HostVars  # noqa: E402


def update_host_vars(path: Path, data_path: str) -> None:
    """Persist the selected MinIO data path back into the host_vars file."""
    raw = yaml.safe_load(path.read_text()) if path.exists() else {}
    host_vars = raw or {}
    host_vars["minio_data_path"] = data_path
    path.write_text(
        "---\n"
        + yaml.dump(
            host_vars,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )
    )


def main() -> None:
    """Ensure MinIO uses external storage or prompt for a replacement path."""
    import questionary

    module = AnsibleModule(
        argument_spec={
            "host": {"type": "str", "required": True},
            "user": {"type": "str", "required": True},
            "key": {"type": "str", "required": False, "no_log": True},
            "port": {"type": "int", "required": False, "default": 22},
            "current_data_path": {"type": "str", "required": True},
            "host_vars_file": {"type": "str", "required": True},
        },
        supports_check_mode=False,
    )

    params = module.params
    current_data_path = params["current_data_path"]

    try:
        connection = make_connection(
            HostVars(
                ansible_host=params["host"],
                ansible_user=params["user"],
                ansible_port=params["port"],
                ansible_ssh_private_key_file=params.get("key"),
            )
        )
        mounts = get_real_mounts(connection)
    except Exception as exc:  # noqa: BLE001
        module.fail_json(msg=str(exc))

    available_mounts = external_mounts(mounts)
    covering_mount = mount_covering(mounts, current_data_path)
    if any(fs.target == covering_mount for fs in available_mounts):
        module.exit_json(changed=False, data_path=current_data_path)

    if not available_mounts:
        module.fail_json(msg="MinIO data path is not on external storage; run `make mount` first.")

    _, subdir_hint = parse_path_hints(current_data_path)

    base_path = flow_use_existing_mount(available_mounts)
    if not base_path:
        module.fail_json(msg="No mount selected.")

    subdir = questionary.text(
        "Subdirectory for MinIO data within the mount:",
        default=subdir_hint or "minio/data",
    ).ask()
    if not subdir:
        module.fail_json(msg="No subdirectory selected.")

    new_path = f"{base_path.rstrip('/')}/{subdir.strip('/')}"

    try:
        update_host_vars(Path(params["host_vars_file"]), new_path)
    except Exception as exc:  # noqa: BLE001
        module.fail_json(msg=str(exc))

    module.exit_json(changed=True, data_path=new_path)


if __name__ == "__main__":
    main()
