"""Database models."""

from app.infrastructure.database.models.shop import Shop
from app.infrastructure.database.models.customer import Customer, CustomerProfile
from app.infrastructure.database.models.conversation import Conversation, Message, MessageAIData, SalesInteraction
from app.infrastructure.database.models.product import Product, ProductVariant, Vehicle, Compatibility
from app.infrastructure.database.models.sales import Recommendation, Lead, Order, OrderItem
from app.infrastructure.database.models.agent import Agent, AgentConfiguration, PromptVersion
from app.infrastructure.database.models.knowledge import KnowledgeDocument, KnowledgeChunk
from app.infrastructure.database.models.sales_knowledge import SalesScenario, SalesDialogue, Objection

__all__ = [
    # Shop
    "Shop",
    # Customer
    "Customer",
    "CustomerProfile",
    # Conversation
    "Conversation",
    "Message", 
    "MessageAIData",
    "SalesInteraction",
    # Product
    "Product",
    "ProductVariant",
    "Vehicle",
    "Compatibility",
    # Sales
    "Recommendation",
    "Lead",
    "Order",
    "OrderItem",
    # Agent
    "Agent",
    "AgentConfiguration",
    "PromptVersion",
    # Knowledge
    "KnowledgeDocument",
    "KnowledgeChunk",
    # Sales Knowledge
    "SalesScenario",
    "SalesDialogue",
    "Objection",
]
