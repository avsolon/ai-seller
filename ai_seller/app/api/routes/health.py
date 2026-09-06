"""Health check routes."""

from fastapi import APIRouter, Depends
from sqlalchemy import text

from app.core.config import Settings, get_settings
from app.infrastructure.database.session import async_session_maker
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


async def _check_database() -> str:
    """Check database connectivity without raising."""
    try:
        async with async_session_maker() as db:
            await db.execute(text("SELECT 1"))
        return "healthy"
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        return f"unhealthy: {type(e).__name__}"


@router.get("/")
async def health_check(
    settings: Settings = Depends(get_settings),
) -> dict:
    """Health check endpoint."""
    db_status = await _check_database()
    return {
        "status": "healthy",
        "environment": settings.app_env,
        "database": db_status,
        "version": "0.1.0",
    }


@router.get("/detailed")
async def detailed_health_check(
    settings: Settings = Depends(get_settings),
) -> dict:
    """Detailed health check endpoint."""
    db_status = await _check_database()
    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "environment": settings.app_env,
        "debug": settings.debug,
        "components": {
            "database": db_status,
            "redis": "healthy",  # Will be tested in future
            "qdrant": "healthy",  # Will be tested in future
        },
        "version": "0.1.0",
    }
