"""Repository layer: interfaces (ports) and SQLAlchemy implementations (adapters)."""

from app.repositories.base import (
    ConversationRepository,
    CustomerRepository,
    MessageRepository,
    ProductRepository,
    SalesStateRepository,
)
from app.repositories.sqlalchemy import (
    SqlConversationRepository,
    SqlCustomerRepository,
    SqlMessageRepository,
    SqlProductRepository,
    SqlSalesStateRepository,
)

__all__ = [
    "CustomerRepository",
    "ConversationRepository",
    "MessageRepository",
    "ProductRepository",
    "SalesStateRepository",
    "SqlCustomerRepository",
    "SqlConversationRepository",
    "SqlMessageRepository",
    "SqlProductRepository",
    "SqlSalesStateRepository",
]
