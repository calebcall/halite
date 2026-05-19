# backend/src/halite/rbac/schemas.py
from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class PermissionOut(BaseModel):
    id: uuid.UUID
    verb: str
    resource_glob: str


class RoleSummary(BaseModel):
    id: uuid.UUID
    name: str
    is_builtin: bool
    description: str


class RoleDetail(RoleSummary):
    permissions: list[PermissionOut]


class RoleListOut(BaseModel):
    total: int
    roles: list[RoleSummary]


class RoleCreatePayload(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    description: str = Field(default="", max_length=255)


class RoleUpdatePayload(BaseModel):
    description: str | None = Field(default=None, max_length=255)


class PermissionPayload(BaseModel):
    verb: str = Field(min_length=1, max_length=64)
    resource_glob: str = Field(min_length=1, max_length=255)


class RoleAssignmentPayload(BaseModel):
    role_id: uuid.UUID
