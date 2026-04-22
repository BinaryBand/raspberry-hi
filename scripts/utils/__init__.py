"""Compatibility shim layer for backwards-compatible imports.

This package re-exports utilities from the canonical linux_hi package to support
legacy import paths. New code should import directly from linux_hi instead.

Re-export modules (thin shims):
- ansible_role_vars: Re-exports from linux_hi.ansible.role_vars
- mount_orchestrator: Re-exports from linux_hi.orchestration.mount
- rclone_controller: Re-exports from linux_hi.orchestration.rclone
- storage_display: Re-exports from linux_hi.storage.display
- storage_policy: Re-exports from linux_hi.storage.policy
- storage_utils: Re-exports from linux_hi.storage

Design pattern modules (intentional definitions):
- connection_types: Protocol definitions for remote command execution
- prompter: Protocol definitions for interactive prompting

Remote-specific implementations:
- storage_discovery: Helper functions for discovering block devices and mounts
  on remote hosts via fabric connections (not in linux_hi as they're fabric-specific)

DEPRECATION PATH:
This compatibility layer will eventually be removed. If you're adding new code,
import directly from linux_hi.* instead of scripts.utils.*.
"""
