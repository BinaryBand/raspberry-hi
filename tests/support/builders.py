"""Factory functions for Pydantic model instances used in tests.

Builders provide sensible defaults so each test only specifies what it cares about.
"""

from __future__ import annotations

from linux_hi.models import BlockDevice, MountInfo


def mnt(
    target: str,
    *,
    source: str = "sda1",
    fstype: str = "ext4",
    size: str = "100G",
) -> MountInfo:
    """Build a MountInfo with a real-looking source/fstype by default."""
    return MountInfo(target=target, source=source, fstype=fstype, size=size)


def blk(
    name: str,
    device_type: str,
    mountpoint: str | None,
    children: list[BlockDevice] | None = None,
    *,
    fstype: str | None = None,
    label: str | None = None,
    size: str = "1T",
) -> BlockDevice:
    """Build a BlockDevice with explicit type and mountpoint."""
    return BlockDevice(
        name=name,
        type=device_type,
        size=size,
        mountpoint=mountpoint,
        children=children,
        fstype=fstype,
        label=label,
    )


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
