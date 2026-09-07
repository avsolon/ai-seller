"""Database models."""

from app.infrastructure.database.models.shop import Shop
from app.infrastructure.database.models.customer import Customer, CustomerProfile, CustomerExternalID
from app.infrastructure.database.models.conversation import Conversation, Message, MessageAIData, SalesInteraction
from app.infrastructure.database.models.product import (
    Product,
    ProductVariant,
    Vehicle,
    Compatibility,
    ProductPrice,
    ProductInventory,
)
from app.infrastructure.database.models.sales import Recommendation, Lead, Order, OrderItem
from app.infrastructure.database.models.agent import Agent, AgentConfiguration, PromptVersion
from app.infrastructure.database.models.knowledge import KnowledgeDocument, KnowledgeChunk
from app.infrastructure.database.models.sales_knowledge import SalesScenario, SalesDialogue, Objection
from app.infrastructure.database.models.sales_state import SalesStateRecord, StateTransition
from app.infrastructure.database.models.agent_run import AgentRun, ToolCall
from app.infrastructure.database.models.feedback import Feedback
from app.infrastructure.database.models.evaluation import EvaluationRun, EvaluationResult
from app.infrastructure.database.models.manager_task import ManagerTask, ManagerTaskStatus

__all__ = [
    # Shop
    "Shop",
    # Customer
    "Customer",
    "CustomerProfile",
    "CustomerExternalID",
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
    "ProductPrice",
    "ProductInventory",
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
    # SalesState / AgentRun
    "SalesStateRecord",
    "StateTransition",
    "AgentRun",
    "ToolCall",
    # Feedback / Evaluation
    "Feedback",
    "EvaluationRun",
    "EvaluationResult",
    # Manager tasks
    "ManagerTask",
    "ManagerTaskStatus",
]
