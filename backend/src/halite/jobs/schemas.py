# backend/src/halite/jobs/schemas.py
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class JobSummary(BaseModel):
    jid: str
    function: str
    target: str
    target_type: str | None = None
    user: str | None = None
    start_time: str | None = None


class JobsListOut(BaseModel):
    total: int
    jobs: list[JobSummary]


class JobMinionResult(BaseModel):
    minion: str
    success: bool | None = None
    retcode: int | None = None
    return_value: Any = None


class JobDetail(BaseModel):
    jid: str
    function: str
    arguments: list[Any] = []
    target: str
    target_type: str | None = None
    user: str | None = None
    start_time: str | None = None
    minions: list[str] = []
    results: list[JobMinionResult] = []
