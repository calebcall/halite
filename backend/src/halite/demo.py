"""Demo-mode seed. Idempotent; only invoked when settings.demo_mode is True.

Creates a read-only `demo` role + user (broad view + Salt actions, but NOT
user/role/settings management — so RBAC alone keeps public visitors read-only),
sets the admin password from env so the operator can still log in and enable
features, and points the Salt connection at the mock with the event stream and
pollers enabled so the demo is live out of the box.
"""
from __future__ import annotations

import secrets
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from halite.auth.models import User
from halite.auth.password import hash_password
from halite.auth.service import _find_user_by_username  # noqa: PLC2701
from halite.config import Settings
from halite.rbac.models import Permission, Role, UserRole
from halite.settings.crypto import encrypt_password
from halite.settings.service import app_settings_row

_DEMO_ROLE = "demo"
_DEMO_USER = "demo"

_DEMO_PERMS: list[tuple[str, str]] = [
    ("view", "*"),
    ("execute", "salt:*"),
    ("run", "*"),
    ("accept", "key:*"), ("reject", "key:*"), ("delete", "key:*"),
    ("kill", "job:*"),
    ("collect", "inventory:*"),
]


async def _ensure_role(session: AsyncSession) -> Role:
    role = (await session.execute(select(Role).where(Role.name == _DEMO_ROLE))).scalar_one_or_none()
    if role is None:
        role = Role(name=_DEMO_ROLE, is_builtin=True,
                    description="Read-only demo visitor: view everything, run Salt, no administration.")
        session.add(role)
        await session.flush()
    existing = {
        (p.verb, p.resource_glob)
        for p in (await session.execute(
            select(Permission).where(Permission.role_id == role.id))).scalars().all()
    }
    for verb, glob in _DEMO_PERMS:
        if (verb, glob) not in existing:
            session.add(Permission(role_id=role.id, verb=verb, resource_glob=glob))
    return role


async def _ensure_demo_user(session: AsyncSession, role: Role) -> None:
    user = await _find_user_by_username(session, _DEMO_USER)
    if user is None:
        user = User(
            username_lower=_DEMO_USER, username=_DEMO_USER,
            # No usable password: the demo user is reached only via the
            # passwordless /api/auth/demo-login route. A random hash prevents
            # logging in as "demo" through the normal login form.
            password_hash=hash_password(secrets.token_urlsafe(32)), display_name="Demo User",
            is_active=True, is_builtin=True, must_change_pw=False,
            created_at=datetime.now(tz=UTC),
        )
        session.add(user)
        await session.flush()
    link = (await session.execute(
        select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id)
    )).scalar_one_or_none()
    if link is None:
        session.add(UserRole(user_id=user.id, role_id=role.id))


async def _set_admin_password(session: AsyncSession, settings: Settings) -> None:
    admin = await _find_user_by_username(session, "admin")
    if admin is not None:
        admin.password_hash = hash_password(settings.demo_admin_password)
        admin.must_change_pw = False


async def _configure_salt(session: AsyncSession, settings: Settings) -> None:
    row = await app_settings_row(session)
    row.salt_api_url = settings.demo_salt_url
    row.salt_api_username = settings.demo_salt_username
    row.salt_api_password_encrypted = encrypt_password(
        settings.demo_salt_password, cookie_secret=settings.cookie_secret)
    row.salt_api_verify = False
    row.salt_api_eauth = "pam"
    row.event_stream_enabled = True
    row.jobs_poll_interval_seconds = 60
    row.fleet_poll_interval_seconds = 120
    row.inventory_refresh_minutes = 10
    row.updated_at = datetime.now(tz=UTC)


async def seed_demo(session: AsyncSession, settings: Settings) -> None:
    role = await _ensure_role(session)
    await _ensure_demo_user(session, role)
    await _set_admin_password(session, settings)
    await _configure_salt(session, settings)
