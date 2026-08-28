"""API module."""

from app.api.routes import api_router
from app.api.dependencies import get_db, get_redis, get_settings

__all__ = ["api_router", "get_db", "get_redis", "get_settings"]
