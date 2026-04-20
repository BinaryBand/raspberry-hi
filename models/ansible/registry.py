from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _empty_preflight_vars() -> dict[str, "PreflightVarSpec"]:
    return {}


def _empty_dependencies() -> list[str]:
    return []


def _empty_vault_secrets() -> list["VaultSecretSpec"]:
    return []


class PreflightVarSpec(BaseModel):
    hint: str = ""
    default: str | None = None
    type: str | None = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_string(cls, value: object) -> object:
        _ = cls
        if isinstance(value, str):
            return {"hint": value}
        return value


class VaultSecretSpec(BaseModel):
    key: str
    label: str
    hidden: bool = False

    model_config = ConfigDict(extra="forbid")


class AppRegistryEntry(BaseModel):
    service_type: Literal["containerized", "tool"]
    backup: bool = False
    restore: bool = False
    cleanup: bool = False
    service_name_var: str | None = None
    dependencies: list[str] = Field(default_factory=_empty_dependencies)
    preflight_vars: dict[str, PreflightVarSpec] = Field(default_factory=_empty_preflight_vars)
    vault_secrets: list[VaultSecretSpec] = Field(default_factory=_empty_vault_secrets)

    model_config = ConfigDict(extra="forbid")


class AppRegistry(BaseModel):
    apps: dict[str, AppRegistryEntry]

    model_config = ConfigDict(extra="forbid")
