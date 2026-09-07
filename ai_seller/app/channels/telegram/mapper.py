"""aiogram Message -> IncomingMessage mapping (doc 12)."""

from __future__ import annotations

from app.channels.dto import (
    Attachment,
    AttachmentType,
    IncomingMessage,
    MessageChannel,
)


class TelegramMapper:
    """Converts an aiogram Message into the channel-neutral IncomingMessage."""

    def to_domain(self, message) -> IncomingMessage:
        attachments = []
        if getattr(message, "photo", None):
            photo = message.photo[-1]
            attachments.append(
                Attachment(
                    type=AttachmentType.IMAGE,
                    external_id=str(photo.file_id),
                    metadata={
                        "width": getattr(photo, "width", None),
                        "height": getattr(photo, "height", None),
                    },
                )
            )
        from_user = getattr(message, "from_user", None)
        return IncomingMessage(
            channel=MessageChannel.TELEGRAM,
            external_user_id=str(getattr(from_user, "id", "")) if from_user else "",
            external_conversation_id=str(getattr(message.chat, "id", "")),
            external_message_id=str(getattr(message, "message_id", "")),
            text=getattr(message, "text", None) or getattr(message, "caption", None),
            attachments=attachments,
            metadata={
                "chat_type": getattr(getattr(message, "chat", None), "type", None),
                "username": getattr(from_user, "username", None) if from_user else None,
            },
        )
