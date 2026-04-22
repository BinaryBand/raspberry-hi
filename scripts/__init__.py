"""CLI wrapper package for backwards-compatible script entrypoints.

TRANSITIONAL INTENT: Scripts in this package are thin entrypoints that delegate
immediately to linux_hi.cli.*. They exist only to preserve legacy invocation paths
(e.g. ``python -m scripts.bootstrap``) while callers are updated.

DO NOT add business logic here. All logic belongs in linux_hi.cli.* or linux_hi.*.

Shim utilities consumed by these scripts live in scripts/utils/ and are
governed by the same constraint — see scripts/utils/__init__.py.
"""
