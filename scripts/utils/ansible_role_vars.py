"""Compatibility shim: re-exports role default variable introspection from canonical location.

DEPRECATED: Import directly from linux_hi.ansible.role_vars instead.
"""

from linux_hi.ansible.role_vars import role_required_vars

__all__ = ["role_required_vars"]
