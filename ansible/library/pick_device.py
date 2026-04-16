#!/usr/bin/python
"""Ansible module that interactively picks an external block device.

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

from ansible.module_utils.basic import AnsibleModule  # noqa: E402
from utils.ansible_utils import make_connection  # noqa: E402
from utils.storage_flows import flow_mount_new_device  # noqa: E402

from models import HostVars  # noqa: E402


def main() -> None:
    """Run the interactive device picker and return the selected device data."""
    module = AnsibleModule(
        argument_spec={
            "host": {"type": "str", "required": True},
            "user": {"type": "str", "required": True},
            "key": {"type": "str", "required": False, "no_log": True},
            "port": {"type": "int", "required": False, "default": 22},
            "label_hint": {"type": "str", "required": False, "default": None},
        },
        supports_check_mode=False,
    )

    params = module.params

    try:
        connection = make_connection(
            HostVars(
                ansible_host=params["host"],
                ansible_user=params["user"],
                ansible_port=params["port"],
                ansible_ssh_private_key_file=params.get("key"),
            )
        )
        result = flow_mount_new_device(connection, label_hint=params.get("label_hint"))
    except Exception as exc:  # noqa: BLE001
        module.fail_json(msg=str(exc))

    if not result:
        module.fail_json(msg="No device selected.")

    device, label = result
    module.exit_json(changed=False, device=device, label=label)


if __name__ == "__main__":
    main()
