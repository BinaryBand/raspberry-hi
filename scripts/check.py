import sys

#!/usr/bin/env python3
"""Compatibility wrapper for the package check entrypoint."""

from linux_hi.cli.check import main

if __name__ == "__main__":
    main(sys.argv[1:])
