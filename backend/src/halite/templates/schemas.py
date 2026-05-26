# backend/src/halite/templates/schemas.py
from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

TargetType = Literal["glob", "list", "pcre", "grain", "nodegroup", "compound"]

_FUN_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*$")


class CommandTemplateBody(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    target: str = Field(min_length=1, max_length=1024)
    target_type: TargetType = "glob"
    fun: str = Field(min_length=1, max_length=128)
    args: list[str] = []
    kwargs: dict[str, Any] = Field(
        default_factory=dict,
        json_schema_extra={"additionalProperties": True},
    )
    is_shared: bool = False

    @field_validator("fun")
    @classmethod
    def _check_fun_shape(cls, v: str) -> str:
        if not _FUN_RE.match(v):
            raise ValueError("fun must be of the form module.function")
        return v


class CommandTemplateCreate(CommandTemplateBody):
    pass


class CommandTemplateOut(CommandTemplateBody):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_user_id: uuid.UUID
    owner_username: str
    created_at: datetime
    updated_at: datetime


class CommandTemplateListOut(BaseModel):
    total: int
    templates: list[CommandTemplateOut]


class TemplateShareUpdate(BaseModel):
    is_shared: bool
