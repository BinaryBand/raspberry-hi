"""CLI entrypoint for repository architectural policy checks."""

from __future__ import annotations

import sys

from linux_hi.models import ANSIBLE_DATA
from linux_hi.policy import PolicyRunner


def main() -> None:
    """Run all repo policy checks and exit non-zero if any fail."""
    failures = PolicyRunner(ANSIBLE_DATA.root).run()
    if failures:
        print("\nREPO POLICY CHECK FAILED:")
        for fail in failures:
            print(f"- {fail}")
        sys.exit(1)
    print("All repo policy checks passed.")


if __name__ == "__main__":
    main()
