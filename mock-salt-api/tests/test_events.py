import asyncio

import pytest

from mock_salt.events import EventBus, format_sse


def test_format_sse_frame():
    frame = format_sse("salt/job/123/new", {"fun": "test.ping"})
    assert frame.startswith("tag: salt/job/123/new\n")
    assert 'data: {"tag": "salt/job/123/new"' in frame
    assert frame.endswith("\n\n")


@pytest.mark.asyncio
async def test_pub_sub_delivers_to_subscriber():
    bus = EventBus()
    with bus.subscribe() as q:
        await bus.publish("salt/key", {"id": "web01.demo.halite", "act": "accept"})
        tag, data = await asyncio.wait_for(q.get(), timeout=1.0)
    assert tag == "salt/key"
    assert data["act"] == "accept"


@pytest.mark.asyncio
async def test_unsubscribe_on_context_exit():
    bus = EventBus()
    with bus.subscribe():
        pass
    assert bus.subscriber_count == 0
