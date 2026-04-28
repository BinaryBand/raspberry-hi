from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PreflightVarSpec(BaseModel):
    hint: str = ""
    default: str | None = None
    type: str | None = None

    model_config = ConfigDict(extra="forbid")


class VaultSecretSpec(BaseModel):
    key: str
    label: str
    hidden: bool = False
    generate: bool = False  # auto-generate a random hex value when the user leaves it blank

    model_config = ConfigDict(extra="forbid")


class AppRegistryEntry(BaseModel):
    service_type: Literal["containerized", "tool"]
    service_name: str | None = None
    image: str | None = None
    port: int | None = None
    runtime_uid: int | None = None
    runtime_gid: int | None = None
    shared_vars: dict[str, str] = Field(default_factory=dict)
    backup: bool = False
    restore: bool = False
    cleanup: bool = False
    dependencies: list[str] = Field(default_factory=list)
    preflight_vars: dict[str, PreflightVarSpec] = Field(default_factory=dict)
    vault_secrets: list[VaultSecretSpec] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class AppRegistry(BaseModel):
    global_vars: dict[str, str] = Field(default_factory=dict)
    apps: dict[str, AppRegistryEntry]

    model_config = ConfigDict(extra="forbid")
