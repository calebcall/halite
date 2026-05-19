# backend/src/halite/users/schemas.py
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserSummary(BaseModel):
    id: uuid.UUID
    username: str
    display_name: str
    email: str | None
    is_active: bool
    is_builtin: bool
    must_change_pw: bool
    created_at: datetime
    last_login_at: datetime | None


class UserListOut(BaseModel):
    total: int
    users: list[UserSummary]


class UserCreatePayload(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    display_name: str = Field(default="", max_length=255)
    email: EmailStr | None = None
    password: str = Field(min_length=8, max_length=1024)
    must_change_pw: bool = True
    role_ids: list[uuid.UUID] = Field(default_factory=list)


class UserUpdatePayload(BaseModel):
    display_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = None
    is_active: bool | None = None


class PasswordResetPayload(BaseModel):
    new_password: str = Field(min_length=8, max_length=1024)
    must_change_pw: bool = True


class ChangePasswordPayload(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=1024)
