"""Canonical JSON payloads for remote command output.

These mirror the exact structure returned by lsblk -J and findmnt -J on a
generic Linux system with one system disk (sda) and one external drive (sdb).
"""

import json

_SYSTEM_DISK = {
    "name": "sda",
    "size": "32G",
    "type": "disk",
    "mountpoint": None,
    "label": None,
    "fstype": None,
    "children": [
        {
            "name": "sda1",
            "size": "500M",
            "type": "part",
            "mountpoint": "/boot/efi",
            "label": "bootfs",
            "fstype": "vfat",
        },
        {
            "name": "sda2",
            "size": "31G",
            "type": "part",
            "mountpoint": "/",
            "label": "rootfs",
            "fstype": "ext4",
        },
    ],
}

_USB_DISK = {
    "name": "sdb",
    "size": "1T",
    "type": "disk",
    "mountpoint": None,
    "label": None,
    "fstype": None,
    "children": [
        {
            "name": "sdb1",
            "size": "1T",
            "type": "part",
            "mountpoint": "/mnt/usb",
            "label": "storage",
            "fstype": "ext4",
        },
    ],
}

# findmnt -J -o TARGET,SOURCE,FSTYPE,SIZE --real
FINDMNT_OUTPUT = json.dumps(
    {
        "filesystems": [
            {"target": "/", "source": "/dev/sda2", "fstype": "ext4", "size": "30G"},
            {
                "target": "/boot/efi",
                "source": "/dev/sda1",
                "fstype": "vfat",
                "size": "500M",
            },
            {"target": "/mnt/usb", "source": "/dev/sdb1", "fstype": "ext4", "size": "1T"},
            {"target": "/run/user/1000", "source": "tmpfs", "fstype": "tmpfs", "size": "400M"},
        ]
    }
)

# lsblk -J -o NAME,SIZE,TYPE,MOUNTPOINT,LABEL,FSTYPE
LSBLK_OUTPUT = json.dumps(
    {
        "blockdevices": [
            _SYSTEM_DISK,
            _USB_DISK,
        ]
    }
)

SYSTEM_ONLY_LSBLK_OUTPUT = json.dumps({"blockdevices": [_SYSTEM_DISK]})
