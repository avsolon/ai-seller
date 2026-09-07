"""Telegram router/handlers (doc 12): no business logic here."""

from __future__ import annotations

from app.core.logging import get_logger

logger = get_logger(__name__)

START_TEXT = (
    "Здравствуйте!\n\n"
    "Помогу подобрать LED/BI-LED линзы для вашего автомобиля.\n\n"
    "Напишите марку, модель и год автомобиля."
)


def build_router(mapper, service, adapter):
    """Build an aiogram Router wired to neutral services.

    Requires the `aiogram` package (raises ImportError when unavailable).
    """
    from aiogram import F, Router
    from aiogram.filters import Command
    from aiogram.types import Message

    router = Router()

    @router.message(Command("start"))
    async def start_handler(message: Message):
        await adapter.send_text(message.chat.id, START_TEXT)

    @router.message(Command("help"))
    async def help_handler(message: Message):
        await adapter.send_text(
            message.chat.id,
            "Напишите, для какого автомобиля ищете линзы, и я помогу подобрать. "
            "Команда /manager — позвать менеджера.",
        )

    @router.message(Command("manager"))
    async def manager_handler(message: Message):
        from app.infrastructure.database.session import get_async_session_context

        async with get_async_session_context() as db:
            incoming = mapper.to_domain(message)
            resolver = service.resolver
            conversation = await resolver.resolve(db, incoming)
            await service.request_handoff(db, conversation, reason="customer_requested_manager")
        await adapter.send_text(message.chat.id, "Хорошо, передаю ваш вопрос менеджеру.")

    @router.message(F.text | F.photo)
    async def message_handler(message: Message):
        incoming = mapper.to_domain(message)
        if not incoming.text and not incoming.attachments:
            return
        async with get_async_session_context() as db:
            await adapter.send_typing(message.chat.id)
            response = await service.handle(db, incoming)
        if response.text:
            await adapter.send_text(message.chat.id, response.text)

    return router
