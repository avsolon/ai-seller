"""Conversation Memory - manages conversation context and history."""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

import redis.asyncio as redis
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.infrastructure.database.models.conversation import Message, Conversation
from app.infrastructure.database.session import get_async_session

logger = get_logger(__name__)


class ConversationMemory:
    """Manages conversation memory using Redis and PostgreSQL."""

    def __init__(self):
        """Initialize conversation memory."""
        self.redis: Optional[redis.Redis] = None

    async def initialize(self) -> None:
        """Initialize Redis connection."""
        self.redis = redis.from_url(settings.redis_url, decode_responses=True)

    async def close(self) -> None:
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()
            self.redis = None

    async def get_recent_messages(
        self, conversation_id: UUID, limit: int = 10
    ) -> List[Message]:
        """Get recent messages from a conversation."""
        try:
            async with get_async_session() as db:
                result = await db.execute(
                    select(Message)
                    .where(Message.conversation_id == conversation_id)
                    .order_by(desc(Message.created_at))
                    .limit(limit)
                )
                messages = result.scalars().all()
                return list(messages)
        except Exception as e:
            logger.error(f"Error getting recent messages: {e}")
            return []

    async def get_conversation_summary(self, conversation_id: UUID) -> Optional[str]:
        """Get conversation summary from Redis."""
        try:
            if not self.redis:
                await self.initialize()
            
            key = f"conversation:{conversation_id}:summary"
            summary = await self.redis.get(key)
            return summary
        except Exception as e:
            logger.error(f"Error getting conversation summary: {e}")
            return None

    async def set_conversation_summary(
        self, conversation_id: UUID, summary: str, ttl: int = 3600
    ) -> None:
        """Set conversation summary in Redis."""
        try:
            if not self.redis:
                await self.initialize()
            
            key = f"conversation:{conversation_id}:summary"
            await self.redis.setex(key, ttl, summary)
        except Exception as e:
            logger.error(f"Error setting conversation summary: {e}")

    async def get_customer_facts(self, customer_id: UUID) -> Dict[str, Any]:
        """Get customer facts from Redis."""
        try:
            if not self.redis:
                await self.initialize()
            
            key = f"customer:{customer_id}:facts"
            facts_json = await self.redis.get(key)
            if facts_json:
                import json
                return json.loads(facts_json)
            return {}
        except Exception as e:
            logger.error(f"Error getting customer facts: {e}")
            return {}

    async def set_customer_facts(
        self, customer_id: UUID, facts: Dict[str, Any], ttl: int = 86400
    ) -> None:
        """Set customer facts in Redis."""
        try:
            if not self.redis:
                await self.initialize()
            
            key = f"customer:{customer_id}:facts"
            import json
            await self.redis.setex(key, ttl, json.dumps(facts, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Error setting customer facts: {e}")

    async def get_current_state(self, conversation_id: UUID) -> Dict[str, Any]:
        """Get current conversation state from Redis."""
        try:
            if not self.redis:
                await self.initialize()
            
            key = f"conversation:{conversation_id}:state"
            state_json = await self.redis.get(key)
            if state_json:
                import json
                return json.loads(state_json)
            return {}
        except Exception as e:
            logger.error(f"Error getting conversation state: {e}")
            return {}

    async def set_current_state(
        self, conversation_id: UUID, state: Dict[str, Any], ttl: int = 3600
    ) -> None:
        """Set current conversation state in Redis."""
        try:
            if not self.redis:
                await self.initialize()
            
            key = f"conversation:{conversation_id}:state"
            import json
            await self.redis.setex(key, ttl, json.dumps(state, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Error setting conversation state: {e}")

    async def get_session_context(self, session_id: str) -> Dict[str, Any]:
        """Get session context from Redis."""
        try:
            if not self.redis:
                await self.initialize()
            
            key = f"session:{session_id}:context"
            context_json = await self.redis.get(key)
            if context_json:
                import json
                return json.loads(context_json)
            return {}
        except Exception as e:
            logger.error(f"Error getting session context: {e}")
            return {}

    async def set_session_context(
        self, session_id: str, context: Dict[str, Any], ttl: int = 1800
    ) -> None:
        """Set session context in Redis."""
        try:
            if not self.redis:
                await self.initialize()
            
            key = f"session:{session_id}:context"
            import json
            await self.redis.setex(key, ttl, json.dumps(context, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Error setting session context: {e}")

    async def clear_conversation_memory(self, conversation_id: UUID) -> None:
        """Clear conversation memory from Redis."""
        try:
            if not self.redis:
                await self.initialize()
            
            # Delete all keys for this conversation
            pattern = f"conversation:{conversation_id}:*"
            keys = await self.redis.keys(pattern)
            if keys:
                await self.redis.delete(*keys)
        except Exception as e:
            logger.error(f"Error clearing conversation memory: {e}")

    async def get_last_message_time(self, conversation_id: UUID) -> Optional[datetime]:
        """Get the time of the last message in a conversation."""
        try:
            async with get_async_session() as db:
                result = await db.execute(
                    select(Message.created_at)
                    .where(Message.conversation_id == conversation_id)
                    .order_by(desc(Message.created_at))
                    .limit(1)
                )
                last_time = result.scalar_one_or_none()
                return last_time
        except Exception as e:
            logger.error(f"Error getting last message time: {e}")
            return None

    async def update_conversation_activity(self, conversation_id: UUID) -> None:
        """Update conversation last activity time."""
        try:
            async with get_async_session() as db:
                result = await db.execute(
                    select(Conversation)
                    .where(Conversation.id == conversation_id)
                )
                conversation = result.scalar_one_or_none()
                if conversation:
                    conversation.last_message_at = datetime.utcnow()
                    await db.flush()
                    await db.refresh(conversation)
        except Exception as e:
            logger.error(f"Error updating conversation activity: {e}")
