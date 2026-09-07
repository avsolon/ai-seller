"""Telegram bot bootstrap (doc 12): aiogram Bot + Dispatcher with handlers."""

from __future__ import annotations

from app.core.logging import get_logger

logger = get_logger(__name__)


def create_bot(token: str):
    """Create aiogram Bot/Dispatcher and register telegram handlers.

    Requires the `aiogram` package; raises ImportError when it is unavailable.
    """
    from aiogram import Bot, Dispatcher

    from app.channels.service import MessageApplicationService
    from app.channels.telegram.adapter import TelegramAdapter
    from app.channels.telegram.handlers import build_router
    from app.channels.telegram.mapper import TelegramMapper

    bot = Bot(token=token)
    dispatcher = Dispatcher()

    service = MessageApplicationService()
    adapter = TelegramAdapter(bot)
    router = build_router(
        mapper=TelegramMapper(),
        service=service,
        adapter=adapter,
    )
    dispatcher.include_router(router)
    return bot, dispatcher
