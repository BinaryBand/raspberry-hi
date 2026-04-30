"""Ports and adapter implementations for interactive workflows."""

from .connection_types import CommandResult, RemoteConnection
from .info_port import InfoPort, RemoteInfoPort
from .prompt_handlers import (
    PasswordHandler,
    PromptHandler,
    PromptRegistry,
    PromptRegistryPort,
    TextHandler,
)
from .prompter import Prompter, QuestionaryPrompter

__all__ = [
    "CommandResult",
    "InfoPort",
    "PasswordHandler",
    "PromptHandler",
    "PromptRegistry",
    "PromptRegistryPort",
    "Prompter",
    "QuestionaryPrompter",
    "RemoteConnection",
    "RemoteInfoPort",
    "TextHandler",
]
