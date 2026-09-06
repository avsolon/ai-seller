"""Repository layer tests against an in-memory SQLite database."""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.base import Base
from app.infrastructure.database.models.agent import Agent
from app.infrastructure.database.models.conversation import (
    Conversation,
    Message,
    MessageType,
    SalesState,
    SenderType,
)
from app.infrastructure.database.models.customer import Customer
from app.infrastructure.database.models.product import Product
from app.infrastructure.database.models.sales_state import SalesStateRecord
from app.infrastructure.database.models.shop import Shop, ShopStatus
from app.repositories.sqlalchemy import (
    SqlConversationRepository,
    SqlCustomerRepository,
    SqlMessageRepository,
    SqlProductRepository,
    SqlSalesStateRepository,
)


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


async def make_shop(db) -> Shop:
    shop = Shop(
        slug="repo-shop",
        name="Repo Test Shop",
        status=ShopStatus.ACTIVE,
        timezone="UTC",
        default_language="ru",
    )
    db.add(shop)
    await db.flush()
    return shop


async def make_customer(db, shop: Shop) -> Customer:
    customer = Customer(shop_id=shop.id, name="Repo Customer")
    db.add(customer)
    await db.flush()
    return customer


async def make_agent(db, shop: Shop) -> Agent:
    agent = Agent(shop_id=shop.id, name="Repo Agent", status="active")
    db.add(agent)
    await db.flush()
    return agent


class TestCustomerRepository:
    async def test_create_and_find_by_external(self, db_session):
        shop = await make_shop(db_session)
        repo = SqlCustomerRepository(db_session)
        customer = await repo.create(Customer(shop_id=shop.id, name="Иван"))
        await repo.add_external_id(customer.id, "telegram", "123456")

        found = await repo.find_by_external("telegram", "123456")
        assert found is not None and found.id == customer.id
        assert await repo.find_by_external("website", "nope") is None


class TestProductRepository:
    async def test_upsert_and_search(self, db_session):
        shop = await make_shop(db_session)
        repo = SqlProductRepository(db_session)
        product = Product(
            shop_id=shop.id,
            sku="ORION-NEPTUN-3",
            name="ORIONLIGHT NEPTUN 3 12V 5000K",
            slug="orion-neptun-3",
            brand="ORIONLIGHT",
            category="Би-лед модули",
            price=10900,
            currency="RUB",
            stock_quantity=10,
            is_active=True,
        )
        db_session.add(product)
        await db_session.flush()

        assert (await repo.get_by_sku(shop.id, "ORION-NEPTUN-3")).id == product.id
        found = await repo.search(shop_id=shop.id, search="neptun")
        assert len(found) == 1


class TestConversationAndMessages:
    async def test_conversation_and_messages(self, db_session):
        shop = await make_shop(db_session)
        customer = await make_customer(db_session, shop)
        agent = await make_agent(db_session, shop)

        conv_repo = SqlConversationRepository(db_session)
        msg_repo = SqlMessageRepository(db_session)

        conversation = Conversation(
            shop_id=shop.id,
            customer_id=customer.id,
            agent_id=agent.id,
            channel="telegram",
            status="active",
            sales_state=SalesState.NEW,
        )
        await conv_repo.create(conversation)

        active = await conv_repo.get_active_by_customer(customer.id, channel="telegram")
        assert active is not None and active.id == conversation.id

        await msg_repo.add(
            Message(
                conversation_id=conversation.id,
                sender_type=SenderType.CUSTOMER,
                message_type=MessageType.TEXT,
                text="Привет",
                meta={},
            )
        )
        await msg_repo.add(
            Message(
                conversation_id=conversation.id,
                sender_type=SenderType.AGENT,
                message_type=MessageType.TEXT,
                text="Здравствуйте!",
                meta={},
            )
        )

        messages = await msg_repo.list_by_conversation(conversation.id, limit=10)
        assert len(messages) == 2
        assert messages[0].sender_type == SenderType.CUSTOMER


class TestSalesStateRepository:
    async def test_upsert_versioning(self, db_session):
        shop = await make_shop(db_session)
        customer = await make_customer(db_session, shop)
        agent = await make_agent(db_session, shop)

        conversation = Conversation(
            shop_id=shop.id,
            customer_id=customer.id,
            agent_id=agent.id,
            channel="web",
            status="active",
            sales_state=SalesState.NEW,
        )
        db_session.add(conversation)
        await db_session.flush()

        repo = SqlSalesStateRepository(db_session)
        state = SalesStateRecord(
            conversation_id=conversation.id,
            stage="NEW",
            vehicle={"make": "BMW"},
            version=1,
        )
        saved = await repo.upsert(state)
        assert saved.version == 1

        saved.stage = "DISCOVERY"
        bumped = await repo.upsert(saved)
        assert bumped.version == 2

        fetched = await repo.get_by_conversation(conversation.id)
        assert fetched is not None and fetched.stage == "DISCOVERY"
