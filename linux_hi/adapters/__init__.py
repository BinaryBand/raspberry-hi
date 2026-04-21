"""Ports and adapter implementations for interactive workflows."""

from .connection_types import CommandResult, RemoteConnection
from .info_port import InfoPort, RemoteInfoPort
from .prompter import Prompter, QuestionaryPrompter

__all__ = [
    "CommandResult",
    "InfoPort",
    "Prompter",
    "QuestionaryPrompter",
    "RemoteConnection",
    "RemoteInfoPort",
]
