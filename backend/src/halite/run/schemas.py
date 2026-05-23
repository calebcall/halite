# backend/src/halite/run/schemas.py
from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

TargetType = Literal["glob", "list", "pcre", "grain", "nodegroup", "compound"]

_FUN_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*$")


class RunCommandIn(BaseModel):
    target: str = Field(min_length=1, max_length=1024)
    target_type: TargetType = "glob"
    fun: str = Field(min_length=1, max_length=128)
    args: list[str] = []
    # `additionalProperties: True` forces openapi-typescript to emit
    # Record<string, unknown> instead of Record<string, never>, so the
    # frontend can pass structured kwarg values (e.g. pillar={"env":"prod"}).
    kwargs: dict[str, Any] = Field(default_factory=dict, json_schema_extra={"additionalProperties": True})

    @field_validator("fun")
    @classmethod
    def _check_fun_shape(cls, v: str) -> str:
        if not _FUN_RE.match(v):
            raise ValueError("fun must be of the form module.function")
        return v


class RunCommandOut(BaseModel):
    jid: str
    minions: list[str]
