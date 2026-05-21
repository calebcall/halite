# backend/src/halite/minions/service.py
from __future__ import annotations

from halite.minions.schemas import MinionSummary
from halite.salt.client import SaltAPIClient


async def list_minions(client: SaltAPIClient) -> list[MinionSummary]:
    connected = await client.list_connected_minions()
    return [MinionSummary(id=mid, ip=ip) for mid, ip in sorted(connected.items())]
