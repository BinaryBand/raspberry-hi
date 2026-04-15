"""Factory functions for Pydantic model instances used in tests.

Builders provide sensible defaults so each test only specifies what it cares about.
"""

from __future__ import annotations

from models import BlockDevice, MountInfo


def mnt(
    target: str,
    *,
    source: str = "sda1",
    fstype: str = "ext4",
    size: str = "100G",
) -> MountInfo:
    """Build a MountInfo with a real-looking source/fstype by default."""
    return MountInfo(target=target, source=source, fstype=fstype, size=size)


def disk(name: str, *, children: list[BlockDevice] | None = None) -> BlockDevice:
    """Build a disk-type BlockDevice."""
    return BlockDevice(name=name, type="disk", size="1T", children=children)


def partition(
    name: str,
    *,
    mountpoint: str | None = None,
    fstype: str = "ext4",
    label: str | None = None,
) -> BlockDevice:
    """Build a partition-type BlockDevice."""
    return BlockDevice(
        name=name,
        type="part",
        size="1T",
        fstype=fstype,
        mountpoint=mountpoint,
        label=label,
    )
