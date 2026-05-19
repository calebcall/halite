"""
Dialect-portable helpers.

Halite uses one query style that works on both Postgres and SQLite. Anywhere a
PG-only operator or type would be tempting, route through this module instead.

Today: case-insensitive equality via lowercased indexed columns. More helpers
land here as needed.
"""
from sqlalchemy import ColumnElement


def lower_eq(column: ColumnElement, value: str) -> ColumnElement:
    """Equality comparison against the lower-cased input.

    The column is expected to already hold lowercased values (e.g. username_lower).
    We only lower() the input on each call.
    """
    return column == value.lower()
