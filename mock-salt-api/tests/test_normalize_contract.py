import sys
from pathlib import Path

import pytest

# Import Halite's normalizer directly from the sibling backend (stdlib-only module).
_BACKEND_SRC = Path(__file__).resolve().parents[2] / "backend" / "src"
sys.path.insert(0, str(_BACKEND_SRC))
from halite.activity.normalize import normalize_event  # noqa: E402

from mock_salt.dispatch import dispatch  # noqa: E402
from mock_salt.events import EventBus  # noqa: E402


async def _collect(fleet, lowstate, n):
    bus = EventBus()
    out = []
    with bus.subscribe() as q:
        await dispatch(fleet, bus, lowstate)
        for _ in range(n):
            out.append(await q.get())
    return out


@pytest.mark.asyncio
async def test_run_events_normalize(fleet):
    body_targets = fleet.present_ids()
    events = await _collect(fleet, {"client": "local_async", "fun": "state.apply",
                                    "tgt": "*", "tgt_type": "glob"},
                            1 + len(body_targets))
    rows = [normalize_event(tag, data) for tag, data in events]
    assert rows[0] is not None and rows[0]["event_type"] == "job.new"
    assert all(r is not None and r["event_type"] == "job.ret" for r in rows[1:])
    assert rows[1]["category"] == "job"


@pytest.mark.asyncio
async def test_key_accept_events_normalize(fleet):
    pending = next(m for m in fleet.minions.values() if m.key_state == "pending")
    events = await _collect(fleet, {"client": "wheel", "fun": "key.accept",
                                    "match": pending.id}, 2)
    by_type = {}
    for tag, data in events:
        r = normalize_event(tag, data)
        assert r is not None
        by_type[r["event_type"]] = r
    assert "key.accept" in by_type
    assert "minion.start" in by_type
    assert by_type["key.accept"]["minion_id"] == pending.id


@pytest.mark.asyncio
async def test_delete_key_normalizes(fleet):
    target = fleet.accepted_ids()[0]
    events = await _collect(fleet, {"client": "wheel", "fun": "key.delete",
                                    "match": target}, 1)
    r = normalize_event(*events[0])
    assert r is not None and r["event_type"] == "key.delete"
