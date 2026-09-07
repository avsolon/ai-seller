"""SellerAgent orchestrator integration tests (in-memory DB, no LLM/RAG)."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.ai.agent.orchestrator import process_message
from app.ai.sales.taxonomy import SalesStage
from app.infrastructure.database.base import Base
from app.infrastructure.database.models.agent import Agent
from app.infrastructure.database.models.agent_run import AgentRun
from app.infrastructure.database.models.conversation import Conversation
from app.infrastructure.database.models.customer import Customer
from app.infrastructure.database.models.product import Product
from app.infrastructure.database.models.sales_state import SalesStateRecord
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
        slug="orch-shop", name="Orch Test Shop", status=ShopStatus.ACTIVE,
        timezone="UTC", default_language="ru",
    )
    db.add(shop)
    await db.flush()

    customer = Customer(shop_id=shop.id, name="Тест")
    db.add(customer)
    await db.flush()

    agent = Agent(shop_id=shop.id, name="Orch Agent", status="active")
    db.add(agent)
    await db.flush()

    product = Product(
        shop_id=shop.id,
        sku="ORION-NEPTUN-3",
        name="ORIONLIGHT NEPTUN 3 12V 5000K",
        slug="orion-neptun-3",
        brand="ORIONLIGHT",
        category="Би-лед модули",
        price=10900,
        currency="RUB",
        stock_quantity=5,
        is_active=True,
    )
    db.add(product)
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


async def count_runs(db, conversation_id) -> int:
    result = await db.execute(
        select(func.count()).select_from(AgentRun).where(
            AgentRun.conversation_id == conversation_id
        )
    )
    return result.scalar_one()


class TestOrchestrator:
    async def test_greeting_creates_state_and_run(self, db_session):
        conversation = await make_conversation(db_session)
        result = await process_message(db_session, conversation, "Привет, нужны линзы", allow_llm=False)
        assert result["intent"] == "GREETING"
        assert result["reply"]
        assert result["stage"] == SalesStage.DISCOVERY.value

        record = (
            await db_session.execute(
                select(SalesStateRecord).where(
                    SalesStateRecord.conversation_id == conversation.id
                )
            )
        ).scalar_one()
        assert record.stage == "DISCOVERY"
        assert conversation.sales_state == "DISCOVERY"
        assert await count_runs(db_session, conversation.id) == 1

    async def test_vehicle_message_fills_state(self, db_session):
        conversation = await make_conversation(db_session)
        result = await process_message(db_session, conversation, "BMW X5 2015, ксенон", allow_llm=False)
        state = result["state"]
        assert state.vehicle.make == "Bmw"
        assert state.vehicle.year == 2015
        assert state.vehicle.headlight_type == "xenon"
        assert result["stage"] == SalesStage.VEHICLE_QUALIFICATION.value

    async def test_handoff_sets_status(self, db_session):
        conversation = await make_conversation(db_session)
        result = await process_message(
            db_session, conversation, "Позовите человека, вопрос нестандартный", allow_llm=False
        )
        assert result["handoff"] is True
        assert conversation.status == "handed_off"

    async def test_state_progresses_across_turns(self, db_session):
        conversation = await make_conversation(db_session)
        await process_message(db_session, conversation, "BMW X5 2015, ксенон", allow_llm=False)

        await process_message(
            db_session, conversation, "хочу лучше дальний свет", allow_llm=False
        )
        state = (await process_message(db_session, conversation, "хочу лучше дальний свет", allow_llm=False))["state"]
        assert state.stage == SalesStage.VEHICLE_QUALIFICATION.value
        assert state.need.primary_need == "дальний свет"
