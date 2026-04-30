"""CLI entry point for registry-driven preflight prompting."""

from __future__ import annotations

import os
import sys

from linux_hi.adapters.prompt_handlers import PasswordHandler, PromptRegistry, TextHandler
from linux_hi.orchestration.preflight import (
    AnsibleHostVarsStore,
    AnsibleVaultStore,
    PreflightError,
    PreflightOrchestrator,
)
from models import ANSIBLE_DATA


def _build_registry() -> PromptRegistry:
    from linux_hi.adapters.rclone_prompt import RcloneRemoteHandler

    return PromptRegistry(
        {
            "text": TextHandler(),
            "password": PasswordHandler(),
            "rclone_remote": RcloneRemoteHandler(),
        }
    )


def main(argv: list[str] | None = None) -> None:
    """Prompt for missing role vars and secrets for an app and its dependencies."""
    args = argv if argv is not None else sys.argv[1:]
    if len(args) < 1:
        sys.exit("Usage: preflight.py <app>")
    app = args[0]
    hostname = os.environ.get("HOST")
    if not hostname:
        sys.exit("HOST is required — set HOST=<inventory-alias> and retry.")
    hostname = ANSIBLE_DATA.require_inventory_host(hostname)
    orchestrator = PreflightOrchestrator(
        registry=_build_registry(),
        hv=AnsibleHostVarsStore(),
        vault=AnsibleVaultStore(),
    )
    try:
        orchestrator.run(app, hostname)
    except PreflightError as exc:
        sys.exit(f"  [FAIL]  {exc}")


if __name__ == "__main__":
    main()
