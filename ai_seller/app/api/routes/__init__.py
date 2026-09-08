"""API routes module."""

from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.conversations import router as conversations_router
from app.api.routes.messages import router as messages_router
from app.api.routes.products import router as products_router
from app.api.routes.recommendations import router as recommendations_router
from app.api.routes.leads import router as leads_router
from app.api.routes.orders import router as orders_router
from app.api.routes.widget import router as widget_router
from app.api.routes.telegram import router as telegram_router
from app.api.routes.diagnostics import router as diagnostics_router

# Create main API router
api_router = APIRouter()

# Include sub-routers
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(conversations_router, prefix="/conversations", tags=["conversations"])
api_router.include_router(messages_router, prefix="/conversations", tags=["conversations"])
api_router.include_router(products_router, prefix="/products", tags=["products"])
api_router.include_router(recommendations_router, prefix="/recommendations", tags=["recommendations"])
api_router.include_router(leads_router, prefix="/leads", tags=["leads"])
api_router.include_router(orders_router, prefix="/orders", tags=["orders"])
api_router.include_router(widget_router, prefix="/widget", tags=["widget"])
api_router.include_router(telegram_router, prefix="/telegram", tags=["telegram"])
api_router.include_router(diagnostics_router, prefix="/diagnostics", tags=["diagnostics"])
