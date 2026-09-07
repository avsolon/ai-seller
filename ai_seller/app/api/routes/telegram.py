"""Telegram webhook routes (doc 12): feeds updates into aiogram when available."""

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.core.config import get_settings
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


async def _feed_dispatcher(update: dict) -> bool:
    """Feed a raw Telegram update to aiogram. Returns False when not possible."""
    settings = get_settings()
    if not settings.telegram_bot_token:
        return False
    try:
        from app.channels.telegram.bot import create_bot

        bot, dispatcher = create_bot(settings.telegram_bot_token)
        await dispatcher.feed_raw_update(bot, update)
        return True
    except Exception as e:
        logger.warning(f"aiogram dispatcher unavailable: {e}")
        return False


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    """Receive updates from Telegram and process them through the SellerAgent."""
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

    if update:
        await _feed_dispatcher(update)

    return {"ok": True, "received": bool(update)}
