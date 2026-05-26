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
            ("kill", "job:*"),
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
            ("view", "inventory:*"),
        ],
    ),
}


async def seed_builtin_roles(session: AsyncSession) -> None:
    """Insert the built-in roles + their permissions if missing. Idempotent.

    Both roles and permissions are filled in a gap-filling manner: a role
    is created only if absent, and each (verb, resource_glob) pair is
    inserted only if not already present on the role. This makes the
    seed safe to call on every boot and ensures deployments upgrading
    from earlier plans pick up newly-added permissions on built-in roles.
    """
    for name, (description, perms) in BUILTIN_ROLES.items():
        existing = (
            await session.execute(select(Role).where(Role.name == name))
        ).scalar_one_or_none()
        if existing is None:
            role = Role(name=name, is_builtin=True, description=description)
            session.add(role)
            await session.flush()
        else:
            role = existing
        existing_perms = {
            (perm.verb, perm.resource_glob)
            for perm in (
                await session.execute(
                    select(Permission).where(Permission.role_id == role.id)
                )
            ).scalars().all()
        }
        for verb, glob in perms:
            if (verb, glob) not in existing_perms:
                session.add(Permission(role_id=role.id, verb=verb, resource_glob=glob))
