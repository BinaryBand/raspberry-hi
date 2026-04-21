def resolve_executable(name: str) -> str:
def run_resolved(cmd: Iterable[str], /, **kwargs: Any) -> subprocess.CompletedProcess[Any]:
"""Compatibility shim: re-export exec helpers from linux_hi.process.exec."""
from linux_hi.process.exec import *
