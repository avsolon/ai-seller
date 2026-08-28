"""Health check routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.core.config import Settings, get_settings

router = APIRouter()


@router.get("/")
async def health_check(
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Health check endpoint."""
    # Test database connection
    try:
        await db.execute("SELECT 1")
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"
    
    return {
        "status": "healthy",
        "environment": settings.app_env,
        "database": db_status,
        "version": "0.1.0",
    }


@router.get("/detailed")
async def detailed_health_check(
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Detailed health check endpoint."""
    # Test database connection
    try:
        await db.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
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
