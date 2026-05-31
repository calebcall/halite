from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from halite.config import Settings
from halite.deps import get_settings_state

router = APIRouter(prefix="/api", tags=["meta"])


class SiteConfig(BaseModel):
    demo: bool


@router.get("/config")
async def site_config(settings: Annotated[Settings, Depends(get_settings_state)]) -> SiteConfig:
    """Unauthenticated public config so the SPA can adapt (demo banner / auto-login)."""
    return SiteConfig(demo=settings.demo_mode)
