import pytest
from sqlalchemy import select

from halite.audit.models import AuditEntry
from halite.audit.writer import record


@pytest.mark.asyncio
async def test_record_inserts_row(session):
    await record(
        session,
        user_id=None,
        action="salt.run",
        resource="minion:web-01",
        args_json={"fun": "test.ping"},
        salt_jid="20260519000001",
        decision="allow",
        result_code=200,
        duration_ms=42,
    )
    await session.commit()
    rows = (await session.execute(select(AuditEntry))).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.action == "salt.run"
    assert row.resource == "minion:web-01"
    assert row.decision == "allow"
    assert row.salt_jid == "20260519000001"
    assert row.args_json == {"fun": "test.ping"}
    assert row.duration_ms == 42
    assert row.at is not None


@pytest.mark.asyncio
async def test_record_redacts_secret_args(session):
    await record(
        session,
        user_id=None,
        action="auth.login",
        resource="user:alice",
        args_json={"username": "alice", "password": "hunter2", "token": "abc"},
        salt_jid=None,
        decision="allow",
        result_code=200,
    )
    await session.commit()
    row = (await session.execute(select(AuditEntry))).scalars().one()
    assert row.args_json == {"username": "alice", "password": "[REDACTED]", "token": "[REDACTED]"}
