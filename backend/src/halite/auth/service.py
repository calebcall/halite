from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from halite.auth.models import Session, User
from halite.auth.password import verify_password
from halite.db_dialect import lower_eq


@dataclass(frozen=True)
class LoginResult:
    session_id: str
    user: User


async def _find_user_by_username(session: AsyncSession, username: str) -> User | None:
    stmt = select(User).where(lower_eq(User.username_lower, username))
    return (await session.execute(stmt)).scalar_one_or_none()


async def login(
    session: AsyncSession,
    username: str,
    password: str,
    *,
    user_agent: str,
    ip: str,
    ttl_minutes: int = 480,
) -> LoginResult | None:
    user = await _find_user_by_username(session, username)
    if user is None or not user.is_active:
        return None
    if not verify_password(user.password_hash, password):
        return None
    sess = await create_session(
        session, user, user_agent=user_agent, ip=ip, ttl_minutes=ttl_minutes
    )
    user.last_login_at = datetime.now(tz=UTC)
    await session.commit()
    return LoginResult(session_id=sess.id, user=user)


async def create_session(
    session: AsyncSession,
    user: User,
    *,
    user_agent: str,
    ip: str,
    ttl_minutes: int,
) -> Session:
    now = datetime.now(tz=UTC)
    sess = Session(
        id=secrets.token_urlsafe(48),
        user_id=user.id,
        created_at=now,
        expires_at=now + timedelta(minutes=ttl_minutes),
        last_seen_at=now,
        user_agent=user_agent[:512],
        ip=ip[:64],
    )
    session.add(sess)
    return sess


async def lookup_session(session: AsyncSession, session_id: str) -> User | None:
    """Return the User for an active session, or None if expired/missing.

    Attaches the user's accumulated RBAC permissions as a transient
    `permissions_cache` attribute so subsequent permission checks during the
    request don't re-query the DB.
    """
    from halite.auth.permissions_cache import load_permissions_for

    now = datetime.now(tz=UTC)
    stmt = (
        select(Session, User)
        .join(User, User.id == Session.user_id)
        .where(Session.id == session_id)
        .where(Session.expires_at > now)
    )
    row = (await session.execute(stmt)).first()
    if row is None:
        return None
    sess, user = row
    if not user.is_active:
        return None
    user.permissions_cache = await load_permissions_for(session, user)
    sess.last_seen_at = now
    await session.commit()
    return user


async def end_session(session: AsyncSession, session_id: str) -> None:
    await session.execute(delete(Session).where(Session.id == session_id))


async def end_sessions_for_user(
    session: AsyncSession, user_id, *, except_session_id: str | None = None
) -> None:
    stmt = delete(Session).where(Session.user_id == user_id)
    if except_session_id is not None:
        stmt = stmt.where(Session.id != except_session_id)
    await session.execute(stmt)
