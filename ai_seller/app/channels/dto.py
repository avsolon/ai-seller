"""Channel-neutral message DTOs (doc 12): SellerAgent never sees Telegram/Web APIs."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Dict, List, Optional


class MessageChannel(StrEnum):
    TELEGRAM = "telegram"
    WEB = "web"


class AttachmentType(StrEnum):
    IMAGE = "image"
    DOCUMENT = "document"


@dataclass
class Attachment:
    type: AttachmentType
    external_id: str
    file_name: Optional[str] = None
    mime_type: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IncomingMessage:
    channel: MessageChannel
    external_user_id: str
    external_conversation_id: str
    external_message_id: str
    text: Optional[str] = None
    attachments: List[Attachment] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OutgoingMessage:
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
