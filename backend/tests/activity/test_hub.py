import asyncio

import pytest

from halite.activity.hub import EventHub


def _ev(cat="job", etype="job.new"):
    return {"category": cat, "event_type": etype, "summary": "x"}


async def test_recent_returns_ring_in_order():
    hub = EventHub(ring_size=3)
    for i in range(5):
        hub.publish(_ev(etype=f"e{i}"))
    recent = hub.recent()
    assert [e["event_type"] for e in recent] == ["e2", "e3", "e4"]


async def test_subscriber_receives_published_event():
    hub = EventHub()
    q = hub.subscribe()
    try:
        hub.publish(_ev(etype="hello"))
        got = await asyncio.wait_for(q.get(), timeout=1)
        assert got["event_type"] == "hello"
    finally:
        hub.unsubscribe(q)


async def test_unsubscribe_stops_delivery():
    hub = EventHub()
    q = hub.subscribe()
    hub.unsubscribe(q)
    hub.publish(_ev())
    assert q.empty()
