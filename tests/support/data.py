"""Canonical JSON payloads for remote command output.

These mirror the exact structure returned by lsblk -J and findmnt -J on a
Raspberry Pi with one SD card (system) and one external USB drive.
"""

from __future__ import annotations

import json

# findmnt -J -o TARGET,SOURCE,FSTYPE,SIZE --real
FINDMNT_OUTPUT = json.dumps({
    "filesystems": [
        {"target": "/",              "source": "/dev/mmcblk0p2", "fstype": "ext4",  "size": "30G"},
        {"target": "/boot/firmware", "source": "/dev/mmcblk0p1", "fstype": "vfat",  "size": "500M"},
        {"target": "/mnt/usb",       "source": "/dev/sda1",       "fstype": "ext4",  "size": "1T"},
        {"target": "/run/user/1000", "source": "tmpfs",           "fstype": "tmpfs", "size": "400M"},
    ]
})

# lsblk -J -o NAME,SIZE,TYPE,MOUNTPOINT,LABEL,FSTYPE
LSBLK_OUTPUT = json.dumps({
    "blockdevices": [
        {
            "name": "mmcblk0", "size": "32G", "type": "disk",
            "mountpoint": None, "label": None, "fstype": None,
            "children": [
                {"name": "mmcblk0p1", "size": "500M", "type": "part",
                 "mountpoint": "/boot/firmware", "label": "bootfs", "fstype": "vfat"},
                {"name": "mmcblk0p2", "size": "31G",  "type": "part",
                 "mountpoint": "/",              "label": "rootfs", "fstype": "ext4"},
            ],
        },
        {
            "name": "sda", "size": "1T", "type": "disk",
            "mountpoint": None, "label": None, "fstype": None,
            "children": [
                {"name": "sda1", "size": "1T", "type": "part",
                 "mountpoint": "/mnt/usb", "label": "storage", "fstype": "ext4"},
            ],
        },
    ]
})
