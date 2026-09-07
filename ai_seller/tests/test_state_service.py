"""SalesStateService tests: cache + DB sync + transitions."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.ai.sales import MemoryStateCache, SalesStateService
from app.ai.sales.taxonomy import SalesStage
from app.infrastructure.database.base import Base
from app.infrastructure.database.models.agent import Agent
from app.infrastructure.database.models.conversation import Conversation
from app.infrastructure.database.models.customer import Customer
from app.infrastructure.database.models.sales_state import StateTransition
from app.infrastructure.database.models.shop import Shop, ShopStatus


@pytest.fixture
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", poolclass=StaticPool
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def make_conversation(db) -> Conversation:
    shop = Shop(
        slug="svc-shop",
        name="Svc Test Shop",
        status=ShopStatus.ACTIVE,
        timezone="UTC",
        default_language="ru",
    )
    db.add(shop)
    await db.flush()

    customer = Customer(shop_id=shop.id, name="Тест")
    db.add(customer)
    await db.flush()

    agent = Agent(shop_id=shop.id, name="Svc Agent", status="active")
    db.add(agent)
    await db.flush()

    conversation = Conversation(
        shop_id=shop.id,
        customer_id=customer.id,
        agent_id=agent.id,
        channel="web",
        status="active",
        sales_state="NEW",
    )
    db.add(conversation)
    await db.flush()
    return conversation


async def count_transitions(db, conversation_id: int) -> int:
    result = await db.execute(
        select(func.count()).select_from(StateTransition).where(
            StateTransition.conversation_id == conversation_id
        )
    )
    return result.scalar_one()


class TestSalesStateService:
    async def test_load_fresh_state(self, db_session):
        conversation = await make_conversation(db_session)
        service = SalesStateService(db_session, MemoryStateCache())
        state = await service.load(conversation.id)
        assert state.stage == SalesStage.NEW
        assert state.conversation_id == str(conversation.id)

    async def test_save_reload_and_transition(self, db_session):
        conversation = await make_conversation(db_session)
        service = SalesStateService(db_session, MemoryStateCache())

        state = await service.load(conversation.id)
        state.vehicle.make = "BMW"
        state.vehicle.model = "X5"
        state.vehicle.year = 2015
        state.need.primary_need = "лучший свет"
        state.stage = SalesStage.DISCOVERY
        await service.save(state)

        # DB-backed recovery via a fresh (empty) cache
        second = SalesStateService(db_session, MemoryStateCache())
        restored = await second.load(conversation.id)
        assert restored.stage == SalesStage.DISCOVERY
        assert restored.vehicle.make == "BMW"
        assert restored.need.primary_need == "лучший свет"

        # denormalized conversation column updated
        assert conversation.sales_state == SalesStage.DISCOVERY.value
        # first transition NEW -> DISCOVERY recorded
        assert await count_transitions(db_session, conversation.id) == 1

    async def test_save_second_stage_records_transition(self, db_session):
        conversation = await make_conversation(db_session)
        service = SalesStateService(db_session, MemoryStateCache())

        state = await service.load(conversation.id)
        state.vehicle.make = "BMW"
        state.stage = SalesStage.DISCOVERY
        await service.save(state)

        state.stage = SalesStage.PRODUCT_SELECTION
        await service.save(state)

        assert await count_transitions(db_session, conversation.id) == 2

        result = await db_session.execute(
            select(StateTransition)
            .where(StateTransition.conversation_id == conversation.id)
            .order_by(StateTransition.created_at)
        )
        transitions = result.scalars().all()
        assert transitions[0].from_stage == "NEW"
        assert transitions[0].to_stage == "DISCOVERY"
        assert transitions[1].from_stage == "DISCOVERY"
        assert transitions[1].to_stage == "PRODUCT_SELECTION"

    async def test_lock_roundtrip(self, db_session):
        cache = MemoryStateCache()
        service = SalesStateService(db_session, cache)
        conversation = await make_conversation(db_session)

        assert await service.acquire_lock(conversation.id) is True
        assert await service.acquire_lock(conversation.id) is False
        await service.release_lock(conversation.id)
        assert await service.acquire_lock(conversation.id) is True
