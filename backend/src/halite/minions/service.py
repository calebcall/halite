# backend/src/halite/minions/service.py
from __future__ import annotations

from halite.minions.schemas import MinionDetail, MinionStatus, MinionSummary
from halite.salt.client import SaltAPIClient

_STATE_TO_STATUS: dict[str, MinionStatus] = {
    "minions_pre": "pending",
    "minions_rejected": "rejected",
    "minions_denied": "denied",
}


async def list_minions_with_status(client: SaltAPIClient) -> list[MinionSummary]:
    """Compose connected + key-state to produce a unified list."""
    connected = await client.list_connected_minions()
    keys = await client.list_minion_keys()

    out: list[MinionSummary] = []
    accepted = keys.get("minions", [])
    for mid in accepted:
        if mid in connected:
            out.append(MinionSummary(id=mid, ip=connected[mid], status="online"))
        else:
            out.append(MinionSummary(id=mid, ip=None, status="offline"))

    for bucket, status in _STATE_TO_STATUS.items():
        for mid in keys.get(bucket, []):
            out.append(MinionSummary(id=mid, ip=None, status=status))

    out.sort(key=lambda m: m.id)
    return out


async def get_minion_detail(client: SaltAPIClient, minion_id: str) -> MinionDetail | None:
    """Returns full detail for a minion, or None if the minion isn't known."""
    connected = await client.list_connected_minions()
    keys = await client.list_minion_keys()

    if minion_id in keys.get("minions", []):
        if minion_id in connected:
            grains = await client.get_minion_grains(minion_id)
            return MinionDetail(
                id=minion_id, status="online", ip=connected[minion_id], grains=grains
            )
        return MinionDetail(id=minion_id, status="offline", ip=None, grains=None)

    for bucket, status in _STATE_TO_STATUS.items():
        if minion_id in keys.get(bucket, []):
            return MinionDetail(id=minion_id, status=status, ip=None, grains=None)

    return None
