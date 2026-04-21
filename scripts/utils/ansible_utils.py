from __future__ import annotations

"""Compatibility facade for non-store Ansible helpers.

ANSIBLE_DATA in models.ansible.access is the canonical boundary for inventory,
registry, and host_vars state. Keep this module limited to operational helpers.
"""

from utils.ansible_connection import make_connection
from utils.ansible_role_vars import role_required_vars

__all__ = [
    "make_connection",
    "role_required_vars",
]
