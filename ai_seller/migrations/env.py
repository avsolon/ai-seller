"""Alembic environment (async-first, driven by app settings).

The migration URL is derived from app.core.config.settings the same way as the
sync SQLAlchemy engine (asyncpg -> psycopg2, sqlite+aiosqlite -> sqlite), so the
migrations always run against the same database the app targets.
"""

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

# Make `app` importable when alembic runs from anywhere inside the project
_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

from app.core.config import settings  # noqa: E402
from app.infrastructure.database.base import Base  # noqa: E402

# Import all models so they are registered on Base.metadata
import app.infrastructure.database.models  # noqa: E402,F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def sync_url() -> str:
    url = settings.database_sync_url or settings.database_url.replace("asyncpg", "psycopg2")
    if url.startswith("sqlite+aiosqlite"):
        url = url.replace("+aiosqlite", "")
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=sync_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(sync_url(), poolclass=pool.NullPool, future=True)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_schemas=False,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
