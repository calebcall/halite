"""
RBAC permission check.

Permissions are (verb, resource_glob) pairs attached to roles. A user accumulates
the union of permissions from all their roles. `check(user, verb, resource)`
returns True iff at least one permission matches.

Globs use shell-style wildcards (* and ?). They are anchored — the whole string
must match. Use ":" as a namespace separator (e.g. "key:web-*", "minion:db-*").
"""
from __future__ import annotations

import fnmatch
from typing import Protocol


class _UserLike(Protocol):
    permissions_cache: list[tuple[str, str]]
    is_active: bool


def matches_glob(pattern: str, value: str) -> bool:
    return fnmatch.fnmatchcase(value, pattern)


def check(user: _UserLike, verb: str, resource: str) -> bool:
    if not user.is_active:
        return False
    for p_verb, p_resource in user.permissions_cache:
        if matches_glob(p_verb, verb) and matches_glob(p_resource, resource):
            return True
    return False
