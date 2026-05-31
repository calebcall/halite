import pytest

from mock_salt.dispatch import dispatch
from mock_salt.events import EventBus


@pytest.mark.asyncio
async def test_accept_key_mutates_and_emits(fleet):
    pending = next(m for m in fleet.minions.values() if m.key_state == "pending")
    bus = EventBus()
    with bus.subscribe() as q:
        await dispatch(fleet, bus, {"client": "wheel", "fun": "key.accept",
                                    "match": pending.id})
        tag, data = await q.get()
    assert fleet.minions[pending.id].key_state == "accepted"
    assert tag == "salt/key" and data == {"id": pending.id, "act": "accept"}


@pytest.mark.asyncio
async def test_delete_key_removes_minion_and_emits(fleet):
    target = fleet.accepted_ids()[0]
    bus = EventBus()
    with bus.subscribe() as q:
        await dispatch(fleet, bus, {"client": "wheel", "fun": "key.delete",
                                    "match": target})
        tag, data = await q.get()
    assert target not in fleet.minions
    assert tag == "salt/key" and data["act"] == "delete"


@pytest.mark.asyncio
async def test_local_async_run_returns_jid_and_emits_new_then_ret(fleet):
    bus = EventBus()
    events = []
    with bus.subscribe() as q:
        body = await dispatch(fleet, bus, {
            "client": "local_async", "fun": "test.ping", "tgt": "*",
            "tgt_type": "glob", "arg": [], "kwarg": {}})
        ret = body["return"][0]
        assert ret["jid"] and isinstance(ret["minions"], list) and ret["minions"]
        for _ in range(1 + len(ret["minions"])):
            events.append(await q.get())
    tags = [t for t, _ in events]
    assert tags[0] == f"salt/job/{ret['jid']}/new"
    assert all(t == f"salt/job/{ret['jid']}/ret/" + m
               for (t, _), m in zip(events[1:], ret["minions"]))
    assert ret["jid"] in fleet.jobs


@pytest.mark.asyncio
async def test_kill_job_marks_inactive(fleet):
    jid = next(iter(fleet.jobs))
    fleet.jobs[jid].active = True
    await dispatch(fleet, None, {"client": "runner", "fun": "saltutil.kill_job",
                                 "jid": jid})
    assert fleet.jobs[jid].active is False
