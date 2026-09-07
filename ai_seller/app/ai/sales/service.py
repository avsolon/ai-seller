"""SalesState persistence: cache (Redis / in-memory) + DB sync.

Phase 2 wiring:
  load  -> Redis cache  -> sales_states row -> brand new NEW state
  save  -> Redis cache  -> upsert sales_states (version++) -> conversations.sales_state
          -> state_transitions (when the stage changed)

Redis is optional: if it is not installed / reachable the service degrades to an
in-memory cache so the agent still works locally.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.sales.state import (
    NeedState,
    Objection,
    ProductSelection,
    PurchaseState,
    SalesState,
    VehicleState,
)
from app.ai.sales.taxonomy import (
    CustomerEmotion,
    CustomerType,
    coerce_intent,
    coerce_stage,
)
from app.core.config import settings
from app.core.logging import get_logger
from app.infrastructure.database.models.conversation import Conversation
from app.infrastructure.database.models.sales_state import SalesStateRecord, StateTransition
from app.repositories.sqlalchemy import SqlSalesStateRepository

logger = get_logger(__name__)

STATE_KEY_TPL = "conversation:{conversation_id}:state"
LOCK_KEY_TPL = "conversation:{conversation_id}:lock"
DEFAULT_STATE_TTL = 7 * 24 * 3600  # 7 days
DEFAULT_LOCK_TIMEOUT = 30


class StateCache:
    """Tiny abstraction over the hot state store."""

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    async def set(self, key: str, value: Dict[str, Any], ttl: int) -> None:
        raise NotImplementedError

    async def delete(self, key: str) -> None:
        raise NotImplementedError

    async def acquire_lock(self, key: str, timeout: int) -> bool:
        return True

    async def release_lock(self, key: str) -> None:
        pass

    async def close(self) -> None:
        pass


class MemoryStateCache(StateCache):
    """In-memory fallback (used when Redis is unavailable and in tests)."""

    def __init__(self) -> None:
        self._store: Dict[str, Dict[str, Any]] = {}
        self._locks: set = set()

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        return self._store.get(key)

    async def set(self, key: str, value: Dict[str, Any], ttl: int) -> None:
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def acquire_lock(self, key: str, timeout: int) -> bool:
        if key in self._locks:
            return False
        self._locks.add(key)
        return True

    async def release_lock(self, key: str) -> None:
        self._locks.discard(key)


class RedisStateCache(StateCache):
    """Redis-backed cache. Constructs the client lazily on first use."""

    def __init__(self) -> None:
        self._redis: Optional[Any] = None

    async def _client(self):
        if self._redis is None:
            import redis.asyncio as redis  # lazy import

            self._redis = redis.from_url(settings.redis_url, decode_responses=True)
        return self._redis

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        try:
            client = await self._client()
            raw = await client.get(key)
            if not raw:
                return None
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"Redis get failed, treating as miss: {e}")
            return None

    async def set(self, key: str, value: Dict[str, Any], ttl: int) -> None:
        try:
            client = await self._client()
            await client.setex(key, ttl, json.dumps(value, ensure_ascii=False))
        except Exception as e:
            logger.warning(f"Redis set failed: {e}")

    async def delete(self, key: str) -> None:
        try:
            client = await self._client()
            await client.delete(key)
        except Exception as e:
            logger.warning(f"Redis delete failed: {e}")

    async def acquire_lock(self, key: str, timeout: int) -> bool:
        try:
            client = await self._client()
            return bool(await client.set(key, "1", nx=True, ex=timeout))
        except Exception as e:
            logger.warning(f"Redis lock acquire failed: {e}")
            return True

    async def release_lock(self, key: str) -> None:
        try:
            client = await self._client()
            await client.delete(key)
        except Exception as e:
            logger.warning(f"Redis lock release failed: {e}")

    async def close(self) -> None:
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:  # pragma: no cover - depends on redis version
                pass
            self._redis = None


def state_cache() -> StateCache:
    """Build the configured state cache with graceful degradation."""
    try:
        import redis  # noqa: F401

        return RedisStateCache()
    except Exception:
        return MemoryStateCache()


def _record_to_state(record: SalesStateRecord) -> SalesState:
    selected_product = None
    if record.selected_product_id:
        selected_product = ProductSelection(product_id=record.selected_product_id)
    state = SalesState(
        conversation_id=str(record.conversation_id),
        stage=coerce_stage(record.stage),
        intent=coerce_intent(record.intent) if record.intent else None,
        emotion=CustomerEmotion(record.emotion) if record.emotion else None,
        customer_type=CustomerType(record.customer_type) if record.customer_type else None,
        vehicle=VehicleState.from_dict(record.vehicle or {}),
        need=NeedState.from_dict(record.need or {}),
        purchase=PurchaseState.from_dict(record.purchase or {}),
        selected_product=selected_product,
        objections=[Objection.from_dict(o) for o in (record.objections or [])],
        missing_slots=list(record.missing_slots or []),
        purchase_intent_score=float(record.purchase_intent_score or 0.0),
        handoff_requested=bool(record.handoff_requested),
        updated_at=record.updated_at.isoformat() if record.updated_at else None,
    )
    return state


def _as_uuid(value: Any) -> UUID:
    """Coerce a str/UUID conversation id into a UUID for DB columns."""
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


class SalesStateService:
    """Loads/saves SalesState through cache + database, tracking transitions."""

    def __init__(
        self,
        db: AsyncSession,
        cache: Optional[StateCache] = None,
        state_ttl: int = DEFAULT_STATE_TTL,
        lock_timeout: int = DEFAULT_LOCK_TIMEOUT,
    ) -> None:
        self.db = db
        self.cache = cache or state_cache()
        self.state_ttl = state_ttl
        self.lock_timeout = lock_timeout
        self._repo = SqlSalesStateRepository(db)

    def _state_key(self, conversation_id) -> str:
        return STATE_KEY_TPL.format(conversation_id=conversation_id)

    def _lock_key(self, conversation_id) -> str:
        return LOCK_KEY_TPL.format(conversation_id=conversation_id)

    async def acquire_lock(self, conversation_id) -> bool:
        return await self.cache.acquire_lock(self._lock_key(conversation_id), self.lock_timeout)

    async def release_lock(self, conversation_id) -> None:
        await self.cache.release_lock(self._lock_key(conversation_id))

    async def load(self, conversation_id) -> SalesState:
        """Return the current state: cache -> database -> fresh NEW state."""
        key = self._state_key(conversation_id)
        cached = await self.cache.get(key)
        if cached:
            return SalesState.from_dict(cached)

        record = await self._repo.get_by_conversation(_as_uuid(conversation_id))
        if record is not None:
            state = _record_to_state(record)
            await self.cache.set(key, state.to_dict(), self.state_ttl)
            return state

        return SalesState(conversation_id=str(conversation_id), stage=coerce_stage("NEW"))

    async def save(self, state: SalesState, reason: Optional[str] = None) -> SalesState:
        """Persist the state to cache + DB; records a transition when the stage moved."""
        conversation_uuid = _as_uuid(state.conversation_id)
        previous = await self._repo.get_by_conversation(conversation_uuid)
        prev_stage = previous.stage if previous is not None else None

        # Cache
        await self.cache.set(
            self._state_key(state.conversation_id), state.to_dict(), self.state_ttl
        )

        # Database upsert (version bumps inside the repository)
        record = await self._repo.upsert(self._to_record(state, previous))
        state.touch()

        # Conversations denormalized stage + transition history
        conversation = await self.db.get(Conversation, conversation_uuid)
        if conversation is not None:
            conversation.sales_state = state.stage.value
            conversation.status = (
                "handed_off" if state.handoff_requested else conversation.status
            )

        # The implicit starting point of any funnel is NEW
        if prev_stage is None:
            prev_stage = "NEW"

        if prev_stage != state.stage.value:
            transition = StateTransition(
                conversation_id=conversation_uuid,
                from_stage=prev_stage,
                to_stage=state.stage.value,
                trigger=state.intent.value if state.intent else None,
                reason=reason,
                state_snapshot=state.to_dict(),
            )
            await self._repo.add_transition(transition)

        await self.db.flush()
        return state

    def _to_record(
        self, state: SalesState, existing: Optional[SalesStateRecord]
    ) -> SalesStateRecord:
        selected_product_id = None
        if state.selected_product is not None and state.selected_product.product_id:
            selected_product_id = _as_uuid(state.selected_product.product_id)

        data = dict(
            conversation_id=_as_uuid(state.conversation_id),
            stage=state.stage.value,
            intent=state.intent.value if state.intent else None,
            emotion=state.emotion.value if state.emotion else None,
            customer_type=state.customer_type.value if state.customer_type else None,
            vehicle=state.vehicle.to_dict(),
            need=state.need.to_dict(),
            purchase=state.purchase.to_dict(),
            objections=[o.to_dict() for o in state.objections],
            missing_slots=list(state.missing_slots),
            selected_product_id=selected_product_id,
            purchase_intent_score=state.purchase_intent_score,
            handoff_requested=state.handoff_requested,
            version=(existing.version if existing is not None else 0) + 1,
        )
        if existing is not None:
            for field, value in data.items():
                setattr(existing, field, value)
            return existing
        return SalesStateRecord(**data)
