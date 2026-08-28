"""Script to initialize the database with test data."""

import asyncio
import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import select

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.infrastructure.database.session import async_session_maker
from app.infrastructure.database.models.shop import Shop, ShopStatus
from app.infrastructure.database.models.customer import Customer, CustomerProfile
from app.infrastructure.database.models.conversation import (
    Conversation,
    ConversationStatus,
    SalesState,
    SenderType,
    MessageType,
    Message,
)
from app.infrastructure.database.models.product import (
    Product,
    ProductVariant,
    Vehicle,
    Compatibility,
    CompatibilityType,
)
from app.infrastructure.database.models.agent import Agent, AgentConfiguration, AgentStatus
from app.infrastructure.database.models.knowledge import KnowledgeDocument, KnowledgeChunk
from app.infrastructure.database.models.sales_knowledge import SalesScenario, SalesDialogue

logger = get_logger(__name__)


async def create_shop(name: str = "Test Shop", slug: str = "test-shop") -> Shop:
    """Create a test shop."""
    shop = Shop(
        id=uuid4(),
        name=name,
        slug=slug,
        status=ShopStatus.ACTIVE,
        timezone="UTC",
        default_language="ru",
    )
    return shop


async def create_customer(shop: Shop, name: str = "Test Customer") -> Customer:
    """Create a test customer."""
    customer = Customer(
        id=uuid4(),
        shop_id=shop.id,
        name=name,
        phone="+79991234567",
        email="test@example.com",
        telegram_user_id="123456789",
        telegram_username="test_user",
        last_activity_at=datetime.utcnow(),
    )
    return customer


async def create_customer_profile(customer: Customer) -> CustomerProfile:
    """Create a test customer profile."""
    profile = CustomerProfile(
        id=uuid4(),
        customer_id=customer.id,
        vehicle_id=None,
        budget_min=10000,
        budget_max=30000,
        customer_type="newbie",
        preferences={"light_temperature": 5500, "priority": "brightness"},
        facts={"car": "BMW X5", "year": 2015, "wants_upgrade": True},
    )
    return profile


async def create_agent(shop: Shop) -> Agent:
    """Create a test agent."""
    agent = Agent(
        id=uuid4(),
        shop_id=shop.id,
        name="AI Seller Agent",
        description="Test AI Seller Agent",
        status=AgentStatus.ACTIVE,
    )
    return agent


async def create_agent_configuration(agent: Agent) -> AgentConfiguration:
    """Create a test agent configuration."""
    config = AgentConfiguration(
        id=uuid4(),
        agent_id=agent.id,
        llm_provider="ollama",
        llm_model="llama3.2:3b",
        temperature=0.7,
        max_tokens=2048,
        rag_enabled=True,
        sales_rag_enabled=True,
        rag_top_k=5,
        language="ru",
        tone="professional",
        settings={"max_history_messages": 20, "enable_streaming": True},
    )
    return config


async def create_vehicle() -> Vehicle:
    """Create a test vehicle."""
    vehicle = Vehicle(
        id=uuid4(),
        brand="BMW",
        model="X5",
        generation="F15",
        year_from=2013,
        year_to=2018,
    )
    return vehicle


async def create_product(shop: Shop) -> Product:
    """Create a test product."""
    product = Product(
        id=uuid4(),
        shop_id=shop.id,
        sku="LX-BMW-001",
        name="Bi-LED Lens X",
        slug="bi-led-lens-x",
        description="Высококачественные Bi-LED линзы для автомобилей BMW",
        brand="LightX",
        category="Bi-LED",
        price=18900.00,
        currency="RUB",
        stock_quantity=10,
        specifications={
            "diameter_mm": 70,
            "power_w": 60,
            "temperature_k": 5500,
            "lumens": 12000,
            "warranty_months": 24,
        },
        is_active=True,
    )
    return product


async def create_product_variant(product: Product) -> ProductVariant:
    """Create a test product variant."""
    variant = ProductVariant(
        id=uuid4(),
        product_id=product.id,
        sku="LX-BMW-001-3.0",
        name="Bi-LED Lens X 3.0",
        price=18900.00,
        attributes={"diameter": "3.0", "temperature": "5500K", "power": "60W"},
        stock_quantity=5,
        is_active=True,
    )
    return variant


async def create_compatibility(product: Product, vehicle: Vehicle) -> Compatibility:
    """Create a test compatibility record."""
    compatibility = Compatibility(
        id=uuid4(),
        product_id=product.id,
        vehicle_id=vehicle.id,
        type=CompatibilityType.DIRECT,
        notes="Прямая совместимость",
        is_confirmed=True,
    )
    return compatibility


async def create_conversation(
    shop: Shop, customer: Customer, agent: Agent
) -> Conversation:
    """Create a test conversation."""
    conversation = Conversation(
        id=uuid4(),
        shop_id=shop.id,
        customer_id=customer.id,
        agent_id=agent.id,
        channel="web",
        external_session_id="test_session_001",
        status=ConversationStatus.ACTIVE,
        sales_state=SalesState.NEW,
        summary="Тестовый диалог",
        started_at=datetime.utcnow(),
        last_message_at=datetime.utcnow(),
    )
    return conversation


async def create_message(conversation: Conversation, text: str, sender: str = "customer") -> Message:
    """Create a test message."""
    sender_type = SenderType.CUSTOMER if sender == "customer" else SenderType.AGENT
    
    message = Message(
        id=uuid4(),
        conversation_id=conversation.id,
        sender_type=sender_type,
        message_type=MessageType.TEXT,
        text=text,
        external_message_id=None,
        metadata={},
    )
    return message


async def create_knowledge_document(shop: Shop) -> KnowledgeDocument:
    """Create a test knowledge document."""
    document = KnowledgeDocument(
        id=uuid4(),
        shop_id=shop.id,
        title="Руководство по установке",
        source_type="MANUAL",
        source_uri="/docs/installation_guide.pdf",
        version="1.0",
        status="active",
        metadata={"author": "AI Seller Team"},
    )
    return document


async def create_knowledge_chunk(document: KnowledgeDocument) -> KnowledgeChunk:
    """Create a test knowledge chunk."""
    chunk = KnowledgeChunk(
        id=uuid4(),
        document_id=document.id,
        chunk_index=0,
        content="Для установки светодиодных линз необходимо: 1) Снять старые линзы, 2) Установить новые в тот же цоколь, 3) Проверить правильность подключения.",
        metadata={"page": 1, "section": "installation"},
        qdrant_point_id=None,
    )
    return chunk


async def create_sales_scenario(shop: Shop) -> SalesScenario:
    """Create a test sales scenario."""
    scenario = SalesScenario(
        id=uuid4(),
        shop_id=shop.id,
        name="Работа с ценовым возражением",
        description="Как правильно работать, когда клиент говорит что дорого",
        intent="price_objection",
        sales_stage="objection",
        priority=1,
    )
    return scenario


async def create_sales_dialogue(scenario: SalesScenario, shop: Shop) -> SalesDialogue:
    """Create a test sales dialogue."""
    dialogue = SalesDialogue(
        id=uuid4(),
        scenario_id=scenario.id,
        shop_id=shop.id,
        title="Пример работы с ценовым возражением",
        customer_type="price_sensitive",
        emotion="skeptical",
        sales_stage="objection",
        intent="price_objection",
        goal="justify_value",
        dialogue=[
            {"role": "customer", "text": "Почему так дорого?"},
            {"role": "seller", "text": "Понимаю ваш вопрос. Если сравнивать только цену — да, есть более дешёвые варианты. Но здесь используются оригинальные чипы и качественная оптика."},
        ],
        quality_score=0.95,
        version="1.0",
    )
    return dialogue


async def init_test_data():
    """Initialize test data in the database."""
    setup_logging()
    logger.info("Starting database initialization with test data...")
    
    try:
        async with async_session_maker() as db:
            # Create shop
            shop = await create_shop()
            db.add(shop)
            await db.flush()
            logger.info(f"Created shop: {shop.name}")
            
            # Create customer
            customer = await create_customer(shop)
            db.add(customer)
            await db.flush()
            logger.info(f"Created customer: {customer.name}")
            
            # Create customer profile
            profile = await create_customer_profile(customer)
            db.add(profile)
            await db.flush()
            logger.info(f"Created customer profile for {customer.name}")
            
            # Create agent
            agent = await create_agent(shop)
            db.add(agent)
            await db.flush()
            logger.info(f"Created agent: {agent.name}")
            
            # Create agent configuration
            config = await create_agent_configuration(agent)
            db.add(config)
            await db.flush()
            logger.info(f"Created agent configuration for {agent.name}")
            
            # Create vehicle
            vehicle = await create_vehicle()
            db.add(vehicle)
            await db.flush()
            logger.info(f"Created vehicle: {vehicle.brand} {vehicle.model}")
            
            # Create product
            product = await create_product(shop)
            db.add(product)
            await db.flush()
            logger.info(f"Created product: {product.name}")
            
            # Create product variant
            variant = await create_product_variant(product)
            db.add(variant)
            await db.flush()
            logger.info(f"Created product variant: {variant.name}")
            
            # Create compatibility
            compatibility = await create_compatibility(product, vehicle)
            db.add(compatibility)
            await db.flush()
            logger.info(f"Created compatibility: {product.name} ↔ {vehicle.brand} {vehicle.model}")
            
            # Create conversation
            conversation = await create_conversation(shop, customer, agent)
            db.add(conversation)
            await db.flush()
            logger.info(f"Created conversation: {conversation.id}")
            
            # Create messages
            message1 = await create_message(conversation, "Здравствуйте!", "customer")
            db.add(message1)
            await db.flush()
            
            message2 = await create_message(conversation, "Здравствуйте! Чем могу помочь?", "agent")
            db.add(message2)
            await db.flush()
            logger.info(f"Created messages in conversation {conversation.id}")
            
            # Create knowledge document
            document = await create_knowledge_document(shop)
            db.add(document)
            await db.flush()
            logger.info(f"Created knowledge document: {document.title}")
            
            # Create knowledge chunk
            chunk = await create_knowledge_chunk(document)
            db.add(chunk)
            await db.flush()
            logger.info(f"Created knowledge chunk for document {document.id}")
            
            # Create sales scenario
            scenario = await create_sales_scenario(shop)
            db.add(scenario)
            await db.flush()
            logger.info(f"Created sales scenario: {scenario.name}")
            
            # Create sales dialogue
            dialogue = await create_sales_dialogue(scenario, shop)
            db.add(dialogue)
            await db.flush()
            logger.info(f"Created sales dialogue: {dialogue.title}")
            
            # Commit all changes
            await db.commit()
            
            logger.info("✅ Successfully initialized database with test data!")
            
            # Print summary
            logger.info("\n📊 Database Initialization Summary:")
            logger.info(f"   - Shop: {shop.name}")
            logger.info(f"   - Customer: {customer.name}")
            logger.info(f"   - Agent: {agent.name}")
            logger.info(f"   - Vehicle: {vehicle.brand} {vehicle.model}")
            logger.info(f"   - Product: {product.name}")
            logger.info(f"   - Conversation: {conversation.id}")
            logger.info(f"   - Messages: 2")
            logger.info(f"   - Knowledge Document: {document.title}")
            logger.info(f"   - Sales Scenario: {scenario.name}")
            logger.info(f"   - Sales Dialogue: {dialogue.title}")
            
    except Exception as e:
        logger.error(f"❌ Error initializing database: {e}")
        raise


async def main():
    """Main function."""
    await init_test_data()


if __name__ == "__main__":
    asyncio.run(main())
