"""Business Tools base types (doc 11)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Protocol, runtime_checkable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.sales.state import SalesState
from app.infrastructure.database.models.conversation import Conversation


@dataclass
class ToolContext:
    """Context passed to every tool execution."""

    db: AsyncSession
    conversation: Conversation
    state: SalesState
    customer_id: Optional[UUID] = None


@dataclass
class ToolResult:
    """Uniform result returned by every tool."""

    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self, tool: str) -> Dict[str, Any]:
        return {
            "tool": tool,
            "success": self.success,
            "result": self.data,
            "error": self.error,
        }


@runtime_checkable
class Tool(Protocol):
    """Protocol implemented by all business tools."""

    name: str

    async def execute(
        self, arguments: Dict[str, Any], context: ToolContext
    ) -> ToolResult: ...
