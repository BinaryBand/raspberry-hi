"""Pydantic models for repository policy registry entries.

These reside under :mod:`models` so other modules can import typed
representations of the policy registry without pulling in ancillary code.
"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, ConfigDict, Field


class PolicyEntry(BaseModel):
    id: str | None = None
    status: str | None = None
    controls: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class PolicyRegistry(BaseModel):
    # Pyright may be unable to fully infer pydantic generic internals; silence
    # that specific diagnostic where it occurs in the project.
    policies: List[PolicyEntry] = Field(default_factory=list)  # type: ignore[reportUnknownVariableType]

    model_config = ConfigDict(extra="allow")


__all__ = ["PolicyEntry", "PolicyRegistry"]
