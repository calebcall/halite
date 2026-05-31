import asyncio
import contextlib
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from halite.config import get_settings
from halite.db import Base

# Import every model module so metadata is populated.
# Modules are added by later plan tasks; wrap to keep env.py importable
# while the project skeleton is still incomplete.
with contextlib.suppress(ImportError):
    from halite.auth import models as _auth_models  # noqa: F401

with contextlib.suppress(ImportError):
    from halite.rbac import models as _rbac_models  # noqa: F401

with contextlib.suppress(ImportError):
    from halite.audit import models as _audit_models  # noqa: F401

with contextlib.suppress(ImportError):
    from halite.templates import models as _templates_models  # noqa: F401

with contextlib.suppress(ImportError):
    from halite.fleet import models as _fleet_models  # noqa: F401

with contextlib.suppress(ImportError):
    from halite.jobs import index_model as _jobs_index_model  # noqa: F401

with contextlib.suppress(ImportError):
    from halite.minions import snapshot_model as _minion_snapshot_model  # noqa: F401

with contextlib.suppress(ImportError):
    from halite.settings import models as _settings_models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    # disable_existing_loggers=False: without it, running a migration would
    # disable every app logger created before this point (fileConfig defaults
    # to True). In the test suite that silently muted loggers like
    # halite.inventory.scheduler, so caplog captured nothing in any test that
    # ran after a migration. We only want alembic's own logging config here.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        future=True,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
