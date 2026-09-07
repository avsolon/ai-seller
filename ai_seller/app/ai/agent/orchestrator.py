"""Compatibility wrapper: delegates message processing to SellerAgentCore.

Kept so existing routes/tests that call orchestrator.process_message keep working
while the actual logic lives in app.ai.agent.core.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agent.core import FALLBACK_ACK, SellerAgentCore
from app.infrastructure.database.models.conversation import Conversation
from app.core.logging import get_logger

logger = get_logger(__name__)


async def process_message(
    db: AsyncSession,
    conversation: Conversation,
    text: str,
    products: Optional[List[Any]] = None,
    allow_llm: bool = True,
) -> Dict[str, Any]:
    """Process a customer message end-to-end via the SellerAgent core."""
    agent = SellerAgentCore()
    try:
        return await agent.process_message(
            db=db,
            conversation=conversation,
            text=text,
            products=products,
            allow_llm=allow_llm,
        )
    except Exception as e:
        logger.warning(f"SellerAgent core failed, using fallback reply: {e}")
        return {
            "reply": FALLBACK_ACK,
            "intent": None,
            "stage": None,
            "handoff": False,
            "guard_issues": [],
            "tools": [],
            "state": None,
        }
