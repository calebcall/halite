# backend/src/halite/run/service.py
from __future__ import annotations

from halite.run.schemas import RunCommandIn, RunCommandOut
from halite.salt.client import SaltAPIClient


async def run_command(client: SaltAPIClient, payload: RunCommandIn) -> RunCommandOut:
    result = await client.run_local_async(
        payload.target,
        payload.fun,
        target_type=payload.target_type,
        args=list(payload.args),
        kwargs=dict(payload.kwargs),
    )
    jid = str(result.get("jid") or "")
    minions_raw = result.get("minions") or []
    minions = [str(m) for m in minions_raw if isinstance(m, str | int)]
    return RunCommandOut(jid=jid, minions=minions)
