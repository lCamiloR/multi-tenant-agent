"""
Alembic execution environment configuration.

This file is the Alembic entry point — it is executed automatically
by the `alembic revision` and `alembic upgrade` commands.

Two critical settings here:
1. target_metadata: points to Base.metadata which contains all
   SQLAlchemy models — without this, --autogenerate does not detect tables.
2. async engine: we use AsyncEngine because the driver is asyncpg —
   Alembic has native support for this via run_async_migrations().
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# We import Base and all models so that the metadata
# is populated when --autogenerate inspects the schema.
# IMPORTANT: all models must be imported here,
# otherwise autogenerate will not detect them.
from src.db.base import Base
from src.db.models.procurement import Procurement          # noqa: F401
from src.db.models.procuring_entity import ProcuringEntity  # noqa: F401

# We import settings to get the DATABASE_URL from .env
from src.core.config import SETTINGS

# Reads alembic.ini for logging configuration
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Points to the metadata that contains all tables declared in the models.
# This is what allows --autogenerate to compare the current database state
# with the expected state from the models and generate migrations automatically.
target_metadata = Base.metadata

# Overrides the sqlalchemy.url from alembic.ini with the environment variable.
# This avoids duplicating the connection URL in two places.
config.set_main_option("sqlalchemy.url", SETTINGS.database_url)


def run_migrations_offline() -> None:
    """
    Offline mode: generates migration SQL without connecting to the database.

    Useful for reviewing the SQL before applying, or for environments
    where direct database connection is not available.
    Run with: alembic upgrade head --sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Online mode with async engine.

    We use async_engine_from_config instead of engine_from_config
    because the asyncpg driver does not support synchronous use — attempts
    to use create_engine() with asyncpg result in the error
    'Can't load plugin: sqlalchemy.dialects:driver'.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
