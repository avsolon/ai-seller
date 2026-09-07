"""SellerAgentCore adapter tests: injected LLM + RAG + real catalog tools."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.ai.agent.core import SellerAgentCore
from app.infrastructure.database.base import Base
from app.infrastructure.database.models.agent import Agent
from app.infrastructure.database.models.agent_run import AgentRun, ToolCall
from app.infrastructure.database.models.conversation import Conversation
from app.infrastructure.database.models.customer import Customer
from app.infrastructure.database.models.product import Compatibility, Product, Vehicle
from app.infrastructure.database.models.shop import Shop, ShopStatus


class FakeLLM:
    def __init__(self, text: str):
        self.text = text
        self.calls: list = []

    async def __call__(self, prompt: str):
        self.calls.append(prompt)
        return {"text": self.text, "provider": "fake-llm", "model": "test-1", "latency_ms": 5}


class FakeRetriever:
    def __init__(self):
        self.sales_calls = 0

    async def search_sales_dialogues(self, query=None, intent=None, sales_state=None, limit=3):
        self.sales_calls += 1
        return [
            {
                "id": "pattern-1",
                "label": "positive",
                "intent": intent,
                "sales_stage": sales_state,
                "dialogue": [
                    {"role": "customer", "text": "Дорого"},
                    {"role": "seller", "text": "Понимаю ваш вопрос."},
                ],
            }
        ]

    async def search_knowledge(self, query=None, limit=3):
        return []


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


async def make_env(db, with_compat: bool = False):
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
    if with_compat:
        vehicle = Vehicle(brand="BMW", model="X5", generation="F15", year_from=2013, year_to=2018)
        db.add(vehicle)
        await db.flush()
        db.add(
            Compatibility(
                product_id=product.id,
                vehicle_id=vehicle.id,
                type="direct",
                is_confirmed=True,
                notes="Подтверждено",
            )
        )
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


async def count_rows(db, model, conversation_id):
    result = await db.execute(
        select(func.count()).select_from(model).where(model.conversation_id == conversation_id)
    )
    return result.scalar_one()


async def count_tool_calls(db, run_id):
    result = await db.execute(
        select(func.count()).select_from(ToolCall).where(ToolCall.agent_run_id == run_id)
    )
    return result.scalar_one()


class TestCoreAdapters:
    async def test_llm_and_rag_are_used(self, db_session):
        conversation = await make_env(db_session)
        llm = FakeLLM("Да, могу показать более доступный вариант.")
        rag = FakeRetriever()
        core = SellerAgentCore(llm_gateway=llm, retriever=rag)

        result = await core.process_message(
            db_session, conversation, "Дорого, на Авито дешевле", allow_llm=True
        )
        assert result["reply"] == llm.text
        assert rag.sales_calls == 1
        assert llm.calls, "LLM must be invoked"

        run = (
            await db_session.execute(
                select(AgentRun).where(AgentRun.conversation_id == conversation.id)
            )
        ).scalar_one()
        assert run.model_provider == "fake-llm"
        assert run.response == llm.text

    async def test_tools_audited_in_agent_run(self, db_session):
        conversation = await make_env(db_session)
        llm = FakeLLM("Рекомендую посмотреть NEPTUN.")
        core = SellerAgentCore(llm_gateway=llm, retriever=FakeRetriever())

        result = await core.process_message(
            db_session, conversation, "Посоветуйте линзы, бюджет до 15000", allow_llm=True
        )
        assert any(t["tool"] == "search_products" for t in result["tools"])

        run = (
            await db_session.execute(
                select(AgentRun).where(AgentRun.conversation_id == conversation.id)
            )
        ).scalar_one()
        assert await count_tool_calls(db_session, run.id) >= 1

    async def test_check_compatibility_tool(self, db_session):
        conversation = await make_env(db_session, with_compat=True)
        llm = FakeLLM("Для вашей конфигурации есть подтверждённая совместимость.")
        core = SellerAgentCore(llm_gateway=llm, retriever=FakeRetriever())

        result = await core.process_message(
            db_session, conversation, "BMW X5, эта линза точно подойдёт?", allow_llm=True
        )
        compat = next(
            (t for t in result["tools"] if t["tool"] == "check_compatibility"), None
        )
        assert compat is not None
        assert compat["result"]["verified"] is True
        assert compat["result"]["matches"]
