"""Compatibility shim layer for backwards-compatible imports.

TRANSITIONAL INTENT: This package exists only to preserve legacy import paths
while callers are migrated to linux_hi. It is not a home for new logic.
The end state is deletion of this entire package.

DO NOT add new logic here. New code belongs in linux_hi.*.

--------------------------------------------------------------------
Module classification
--------------------------------------------------------------------

SHIM_MODULES — re-export only; no logic permitted (enforced by TestShimGuard):
- ansible_role_vars: Re-exports from linux_hi.ansible.role_vars
- mount_orchestrator: Re-exports from linux_hi.orchestration.mount
- rclone_controller: Re-exports from linux_hi.orchestration.rclone
- storage_display:   Re-exports from linux_hi.storage.display
- storage_policy:    Re-exports from linux_hi.storage.policy
- storage_utils:     Re-exports from linux_hi.storage

INTENTIONAL_MODULES — allowed to define logic for reasons documented below:
- connection_types:  Protocol definitions for remote command execution
                     (not in linux_hi because linux_hi is local-only)
- prompter:          Protocol definitions for interactive prompting
- storage_discovery: Remote block-device discovery via fabric connections
                     (fabric-specific; not duplicated in linux_hi)
- info_port:         Protocol + adapter for remote device/mount discovery
                     (deprecated; not actively imported, kept for reference)
- yaml_utils:        Thin wrapper for yaml with type-annotated helpers
                     (deprecated; import directly from yaml or ruamel.yaml)

--------------------------------------------------------------------
Machine-readable sets consumed by TestShimGuard in tests/test_lint.py
--------------------------------------------------------------------
"""

# Modules that must contain ONLY re-exports (imports + __all__).
# TestShimGuard fails the build if any of these define a function or class.
SHIM_MODULES: frozenset[str] = frozenset(
    {
        "ansible_role_vars",
        "mount_orchestrator",
        "rclone_controller",
        "storage_display",
        "storage_policy",
        "storage_utils",
    }
)

# Modules that intentionally contain logic (exempt from the shim guard).
INTENTIONAL_MODULES: frozenset[str] = frozenset(
    {
        "connection_types",
        "prompter",
        "storage_discovery",
        "info_port",
        "yaml_utils",
    }
)
