"""SellerAgentCore tests: AgentDecision + full pipeline (no LLM/RAG)."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.ai.agent.core import SellerAgentCore
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


async def make_env(db):
    shop = Shop(
        slug="core-shop", name="Core Test Shop", status=ShopStatus.ACTIVE,
        timezone="UTC", default_language="ru",
    )
    db.add(shop)
    await db.flush()
    customer = Customer(shop_id=shop.id, name="Тест")
    db.add(customer)
    await db.flush()
    agent = Agent(shop_id=shop.id, name="Core Agent", status="active")
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
    return conversation, product


async def count_runs(db, conversation_id) -> int:
    result = await db.execute(
        select(func.count()).select_from(AgentRun).where(
            AgentRun.conversation_id == conversation_id
        )
    )
    return result.scalar_one()


class TestAgentDecisionPipeline:
    async def test_full_pipeline_decides_vehicle_qualification(self, db_session):
        conversation, _ = await make_env(db_session)
        agent = SellerAgentCore()
        result = await agent.process_message(
            db_session, conversation, "BMW X5 2015, ксенон", allow_llm=False
        )
        decision = result["decision"]
        assert decision["intent"] == "VEHICLE_INFO"
        assert decision["stage"] == SalesStage.VEHICLE_QUALIFICATION.value
        assert decision["required_slots"]
        assert decision["confidence"] == 0.9
        assert result["reply"]

    async def test_recommendation_triggers_product_tool(self, db_session):
        conversation, product = await make_env(db_session)
        agent = SellerAgentCore()
        result = await agent.process_message(
            db_session, conversation, "Посоветуйте линзы, бюджет до 15000",
            products=[product], allow_llm=False,
        )
        tools = result["tools"]
        assert any(t["tool"] == "search_products" for t in tools)

    async def test_handoff_decision(self, db_session):
        conversation, _ = await make_env(db_session)
        agent = SellerAgentCore()
        result = await agent.process_message(
            db_session, conversation, "Позовите специалиста", allow_llm=False
        )
        assert result["decision"]["handoff"] is True
        assert result["handoff"] is True
        assert conversation.status == "handed_off"

    async def test_persist_writes_state_and_run(self, db_session):
        conversation, _ = await make_env(db_session)
        agent = SellerAgentCore()
        await agent.process_message(
            db_session, conversation, "Привет", allow_llm=False
        )
        record = (
            await db_session.execute(
                select(SalesStateRecord).where(
                    SalesStateRecord.conversation_id == conversation.id
                )
            )
        ).scalar_one()
        assert record.stage == SalesStage.DISCOVERY.value
        assert await count_runs(db_session, conversation.id) == 1
