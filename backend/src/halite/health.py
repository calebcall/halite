from fastapi import APIRouter
from sqlalchemy import text

from halite.db import SessionDep

router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(db: SessionDep) -> dict:
    checks: dict[str, str] = {}
    try:
        await db.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as exc:
        checks["db"] = f"error: {exc!r}"
    status = "ready" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": status, "checks": checks}
