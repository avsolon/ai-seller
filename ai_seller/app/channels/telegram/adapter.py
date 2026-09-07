"""Telegram output adapter (doc 12): thin wrapper around the aiogram Bot."""

from __future__ import annotations


class TelegramAdapter:
    """Sends typed messages back to Telegram."""

    def __init__(self, bot) -> None:
        self.bot = bot

    async def send_text(self, chat_id, text: str) -> None:
        await self.bot.send_message(chat_id=chat_id, text=text)

    async def send_typing(self, chat_id) -> None:
        await self.bot.send_chat_action(chat_id=chat_id, action="typing")
