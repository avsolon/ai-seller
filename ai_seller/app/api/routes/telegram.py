"""Telegram webhook routes."""

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.core.config import get_settings
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    """Receive updates from Telegram.

    MVP skeleton: validates the webhook secret and acknowledges the update.
    Real message processing (Telegram Adapter) will be wired here later.
    """
    settings = get_settings()

    if settings.telegram_webhook_secret and (
        x_telegram_bot_api_secret_token != settings.telegram_webhook_secret
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid webhook secret"
        )

    try:
        update = await request.json()
    except Exception:
        update = {}

    logger.info(f"Telegram webhook received update_id={update.get('update_id')}")
    return {"ok": True, "received": update.get("update_id") is not None}
