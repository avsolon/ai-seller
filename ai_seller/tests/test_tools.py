"""Business tools (doc 11) tests: registry + selected tool executions."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.ai.agent.core import _route_tools
from app.ai.sales import SalesState
from app.ai.sales.taxonomy import CustomerIntent
from app.ai.tools import ToolContext, build_default_registry
from app.infrastructure.database.base import Base
from app.infrastructure.database.models.agent import Agent
from app.infrastructure.database.models.conversation import Conversation
from app.infrastructure.database.models.customer import Customer
from app.infrastructure.database.models.product import Compatibility, Product, Vehicle
from app.infrastructure.database.models.sales import Lead
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


async def make_env(db, with_compat=False):
    shop = Shop(
        slug="tools-shop", name="Tools Test Shop", status=ShopStatus.ACTIVE,
        timezone="UTC", default_language="ru",
    )
    db.add(shop)
    await db.flush()
    customer = Customer(shop_id=shop.id, name="Тест")
    db.add(customer)
    await db.flush()
    agent = Agent(shop_id=shop.id, name="Tools Agent", status="active")
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
        vehicle = Vehicle(brand="BMW", model="X5", year_from=2013, year_to=2018)
        db.add(vehicle)
        await db.flush()
        db.add(Compatibility(product_id=product.id, vehicle_id=vehicle.id,
                             type="direct", is_confirmed=True))
        await db.flush()
    conversation = Conversation(
        shop_id=shop.id, customer_id=customer.id, agent_id=agent.id,
        channel="web", status="active", sales_state="NEW",
    )
    db.add(conversation)
    await db.flush()
    return conversation


def make_context(db, conversation, **vehicle):
    state = SalesState(conversation_id=str(conversation.id))
    if vehicle.get("make"):
        state.vehicle.make = vehicle["make"]
    if vehicle.get("model"):
        state.vehicle.model = vehicle["model"]
    return ToolContext(db=db, conversation=conversation, state=state,
                       customer_id=conversation.customer_id)


class TestRegistry:
    def test_default_registry_has_mvp_tools(self):
        registry = build_default_registry()
        expected = {
            "get_product", "search_products", "get_product_price", "get_product_stock",
            "check_compatibility", "get_delivery_info", "get_warranty_info",
            "create_lead", "create_order", "request_handoff",
        }
        assert expected.issubset(set(registry.names()))

    def test_unknown_tool_not_registered(self):
        registry = build_default_registry()
        assert registry.get("drop_table") is None


class TestAuthorization:
    def test_routed_tools_are_allowed(self):
        registry = build_default_registry()
        allowed = set(registry.names())
        for intent in CustomerIntent:
            routed = _route_tools(intent)
            assert set(routed).issubset(allowed)
        # representative mappings exist
        assert _route_tools(CustomerIntent.VEHICLE_COMPATIBILITY) == ["check_compatibility"]
        assert _route_tools(CustomerIntent.DELIVERY_QUERY) == ["get_delivery_info"]
        assert _route_tools(CustomerIntent.WARRANTY_QUERY) == ["get_warranty_info"]
        assert _route_tools(CustomerIntent.ORDER_REQUEST) == ["create_order"]


class TestTools:
    async def test_search_products_returns_verified_data(self, db_session):
        conversation = await make_env(db_session)
        registry = build_default_registry()
        result = await registry.get("search_products").execute(
            {"budget": 15000}, make_context(db_session, conversation)
        )
        assert result.success is True
        products = result.data["products"]
        assert products and products[0]["price"] == 10900

    async def test_check_compatibility_confirmed(self, db_session):
        conversation = await make_env(db_session, with_compat=True)
        registry = build_default_registry()
        ctx = make_context(db_session, conversation, make="BMW", model="X5")
        result = await registry.get("check_compatibility").execute({}, ctx)
        assert result.success is True
        assert result.data["verified"] is True
        assert result.data["compatibility"] == "confirmed"

    async def test_check_compatibility_requests_required(self, db_session):
        conversation = await make_env(db_session)
        registry = build_default_registry()
        ctx = make_context(db_session, conversation)
        result = await registry.get("check_compatibility").execute({}, ctx)
        assert result.data["verified"] is False
        assert "headlight_type" in result.data["required"]
        assert "photo" in result.data["required"]

    async def test_create_lead_persists(self, db_session):
        conversation = await make_env(db_session)
        registry = build_default_registry()
        result = await registry.get("create_lead").execute(
            {}, make_context(db_session, conversation)
        )
        assert result.success is True
        count = (
            await db_session.execute(select(func.count()).select_from(Lead))
        ).scalar_one()
        assert count == 1

    async def test_request_handoff_marks_state(self, db_session):
        conversation = await make_env(db_session)
        registry = build_default_registry()
        ctx = make_context(db_session, conversation)
        result = await registry.get("request_handoff").execute({}, ctx)
        assert result.success is True
        assert ctx.state.handoff_requested is True
