"""CLI entrypoint for repository architectural policy checks."""

from __future__ import annotations

from linux_hi.policy_utils import PolicyRunner
from models import ANSIBLE_DATA


def main() -> None:
    """Run all repo policy checks and exit non-zero if any fail."""
    PolicyRunner(ANSIBLE_DATA.root).run()


if __name__ == "__main__":
    main()
