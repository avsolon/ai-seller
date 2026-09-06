"""Database session management."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.logging import get_logger
from app.infrastructure.database.base import Base

logger = get_logger(__name__)


def _is_sqlite(url: str) -> bool:
    """Check whether the database URL points to a SQLite database."""
    return url.startswith("sqlite")


def _sync_database_url() -> str:
    """Derive a synchronous database URL from the configured one."""
    url = settings.database_url
    if _is_sqlite(url):
        # sqlite+aiosqlite has no synchronous driver; use plain sqlite
        return url.replace("+aiosqlite", "")
    return (settings.database_sync_url or url).replace("asyncpg", "psycopg2")


# Async database engine and session
_async_engine_kwargs: dict = {"echo": settings.debug, "pool_pre_ping": True}
if not _is_sqlite(settings.database_url):
    _async_engine_kwargs.update(pool_size=20, max_overflow=10)

async_engine = create_async_engine(settings.database_url, **_async_engine_kwargs)

async_session_maker = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

# Sync database engine and session (optional: requires psycopg2 driver)
_sync_engine_kwargs: dict = {"echo": settings.debug, "pool_pre_ping": True}
if not _is_sqlite(_sync_database_url()):
    _sync_engine_kwargs.update(pool_size=10, max_overflow=5)

try:
    sync_engine = create_engine(_sync_database_url(), **_sync_engine_kwargs)
except ImportError as e:  # pragma: no cover - depends on optional driver
    logger.warning(f"Sync database engine unavailable: {e}")
    sync_engine = None

if sync_engine is not None:
    sync_session_maker = sessionmaker(
        bind=sync_engine,
        class_=Session,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )
else:  # pragma: no cover - depends on optional driver
    sync_session_maker = None


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for async database session."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_async_session_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for async database session."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()


def get_sync_session() -> Generator[Session, None, None]:
    """Dependency for sync database session."""
    if sync_session_maker is None:  # pragma: no cover - depends on optional driver
        raise RuntimeError("Sync database engine is not available (psycopg2 not installed)")
    with sync_session_maker() as session:
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()


async def init_db() -> None:
    """Initialize database tables."""
    # Import all models to ensure they are registered on Base.metadata
    from app.infrastructure.database import models  # noqa: F401

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created")


async def drop_db() -> None:
    """Drop all database tables."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        logger.info("Database tables dropped")
