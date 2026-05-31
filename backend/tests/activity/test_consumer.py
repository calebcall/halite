from sqlalchemy import func, select

from halite.activity.consumer import EventStreamConsumer
from halite.activity.hub import EventHub
from halite.activity.models import ActivityEvent
from halite.jobs.index_model import JobIndexEntry


class _FakeSalt:
    async def stream_events(self):
        yield "salt/minion/web01/start", {"id": "web01"}
        yield "salt/key", {"id": "db07", "act": "accept"}
        yield "salt/beacon/web01/x", {"id": "web01"}  # dropped by normalizer


class _FakeSaltJobNew:
    async def stream_events(self):
        yield (
            "salt/job/20260529120000000000/new",
            {"fun": "test.ping", "tgt": "*", "minions": ["web01"]},
        )


class _FakeSaltJobRet:
    async def stream_events(self):
        # job.ret carrying neither user nor tgt — initiator/target must be
        # backfilled from the jobs_index row seeded in the test.
        yield (
            "salt/job/20260529120000000000/ret/web01",
            {"fun": "test.ping", "id": "web01", "retcode": 0, "return": True},
        )


async def test_consumer_job_ret_backfills_initiator_target(db_sessionmaker):
    from datetime import UTC, datetime

    async with db_sessionmaker() as s:
        s.add(
            JobIndexEntry(
                jid="20260529120000000000",
                function="test.ping",
                target="web*",
                target_type="glob",
                user="alice",
                started_at=datetime.now(tz=UTC),
                seen_at=datetime.now(tz=UTC),
            )
        )
        await s.commit()

    hub = EventHub()
    consumer = EventStreamConsumer(
        salt=_FakeSaltJobRet(),
        sessionmaker=db_sessionmaker,
        hub=hub,
        retention_days=30,
    )
    await consumer._consume_once()
    async with db_sessionmaker() as s:
        row = (
            await s.execute(
                select(ActivityEvent).where(ActivityEvent.event_type == "job.ret")
            )
        ).scalar_one()
    assert row.initiator == "alice"
    assert row.target == "web*"


async def test_consumer_processes_one_batch(db_sessionmaker):
    hub = EventHub()
    consumer = EventStreamConsumer(
        salt=_FakeSalt(),
        sessionmaker=db_sessionmaker,
        hub=hub,
        retention_days=30,
    )
    await consumer._consume_once()  # one pass over the fake stream
    assert len(hub.recent()) == 2  # beacon dropped
    async with db_sessionmaker() as s:
        count = await s.scalar(select(func.count()).select_from(ActivityEvent))
    assert count == 2


async def test_consumer_job_new_upserts_job_index(db_sessionmaker):
    hub = EventHub()
    consumer = EventStreamConsumer(
        salt=_FakeSaltJobNew(),
        sessionmaker=db_sessionmaker,
        hub=hub,
        retention_days=30,
    )
    await consumer._consume_once()
    async with db_sessionmaker() as s:
        row = await s.get(JobIndexEntry, "20260529120000000000")
    assert row is not None
    assert row.function == "test.ping"
