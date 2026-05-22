# backend/src/halite/keys/service.py
from __future__ import annotations

from halite.keys.schemas import KeyEntry, KeyStatus
from halite.salt.client import SaltAPIClient

_BUCKET_TO_STATUS: dict[str, KeyStatus] = {
    "minions": "accepted",
    "minions_pre": "pending",
    "minions_rejected": "rejected",
    "minions_denied": "denied",
}


async def list_keys(client: SaltAPIClient) -> list[KeyEntry]:
    raw = await client.list_minion_keys()
    out: list[KeyEntry] = []
    for bucket, status in _BUCKET_TO_STATUS.items():
        for mid in raw.get(bucket, []):
            out.append(KeyEntry(id=mid, status=status))
    out.sort(key=lambda k: (k.id, k.status))
    return out
