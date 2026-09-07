"""Channel package: neutral DTOs + channel-agnostic messaging application service."""

from app.channels.dto import (
    Attachment,
    AttachmentType,
    IncomingMessage,
    MessageChannel,
    OutgoingMessage,
)
from app.channels.service import ConversationResolver, MessageApplicationService

__all__ = [
    "Attachment",
    "AttachmentType",
    "IncomingMessage",
    "MessageChannel",
    "OutgoingMessage",
    "ConversationResolver",
    "MessageApplicationService",
]
