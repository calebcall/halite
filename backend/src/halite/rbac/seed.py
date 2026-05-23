from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from halite.rbac.models import Permission, Role

BUILTIN_ROLES: dict[str, tuple[str, list[tuple[str, str]]]] = {
    "admin": (
        "Full access to all features and administration.",
        [("*", "*")],
    ),
    "operator": (
        "Run salt commands and manage keys, but no user administration.",
        [
            ("view", "*"),
            ("run", "*"),
            ("accept", "key:*"),
            ("delete", "key:*"),
            ("execute", "salt:*"),
            ("reject", "key:*"),
        ],
    ),
    "viewer": (
        "Read-only access to everything except audit.",
        [
            ("view", "minion:*"),
            ("view", "key:*"),
            ("view", "job:*"),
            ("view", "grain:*"),
            ("view", "pillar:*"),
            ("view", "event:*"),
            ("view", "setting:*"),
        ],
    ),
}


async def seed_builtin_roles(session: AsyncSession) -> None:
    """Insert the built-in roles + their permissions if missing. Idempotent."""
    for name, (description, perms) in BUILTIN_ROLES.items():
        existing = (
            await session.execute(select(Role).where(Role.name == name))
        ).scalar_one_or_none()
        if existing is None:
            role = Role(name=name, is_builtin=True, description=description)
            session.add(role)
            await session.flush()
            for verb, glob in perms:
                session.add(Permission(role_id=role.id, verb=verb, resource_glob=glob))
