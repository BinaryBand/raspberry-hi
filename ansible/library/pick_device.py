#!/usr/bin/python
"""Ansible module that interactively picks an external block device."""

from __future__ import annotations

from ansible.module_utils.basic import AnsibleModule
from utils.ansible_utils import make_connection
from utils.storage_flows import flow_mount_new_device

from models import HostVars


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
