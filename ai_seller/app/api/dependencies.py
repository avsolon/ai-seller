"""API dependencies."""

from typing import Annotated, AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from app.core.config import Settings, get_settings
from app.infrastructure.database.session import get_async_session
from app.core.logging import get_logger

logger = get_logger(__name__)


# Database dependency
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    async for session in get_async_session():
        yield session


# Redis dependency
@asynccontextmanager
async def get_redis_connection() -> AsyncGenerator[redis.Redis, None]:
    """Get Redis connection."""
    settings = get_settings()
    try:
        connection = redis.from_url(settings.redis_url, decode_responses=True)
        yield connection
        await connection.close()
    except Exception as e:
        logger.error(f"Redis connection error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Redis connection failed",
        )


async def get_redis() -> AsyncGenerator[redis.Redis, None]:
    """Get Redis connection dependency."""
    async with get_redis_connection() as connection:
        yield connection


# Settings dependency
def get_settings_dependency() -> Settings:
    """Get settings dependency."""
    return get_settings()


# API Key authentication
async def get_api_key(
    x_api_key: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings_dependency),
) -> str:
    """Validate API key."""
    if x_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )
    
    if settings.widget_api_key and x_api_key != settings.widget_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    
    return x_api_key


# Shop ID dependency
async def get_shop_id(
    x_shop_id: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings_dependency),
) -> str:
    """Get shop ID from header or use default."""
    return x_shop_id or settings.shop_id


# Annotated types for cleaner imports
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]
RedisConnection = Annotated[redis.Redis, Depends(get_redis)]
AppSettings = Annotated[Settings, Depends(get_settings_dependency)]
ApiKey = Annotated[str, Depends(get_api_key)]
ShopId = Annotated[str, Depends(get_shop_id)]
