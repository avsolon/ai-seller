"""Pytest configuration and fixtures."""

import asyncio
from typing import AsyncGenerator, Generator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings, get_settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.session import async_session_maker, get_async_session
from app.main import app
from fastapi.testclient import TestClient


# Test settings
@pytest.fixture
def test_settings() -> Settings:
    """Test settings fixture."""
    return Settings(
        app_env="testing",
        debug=True,
        secret_key="test-secret-key",
        database_url="sqlite+aiosqlite:///:memory:",
        redis_url="redis://localhost:6379/0",
        qdrant_url="http://localhost:6333",
        llm_provider="ollama",
        ollama_base_url="http://localhost:11434",
        shop_id="test-shop",
        default_language="ru",
        default_currency="RUB",
    )


# Database fixtures
@pytest.fixture(scope="session")
def test_db_engine():
    """Create test database engine."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    return engine


@pytest.fixture(scope="session")
async def test_db_setup(test_db_engine):
    """Setup test database."""
    async with test_db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield
    
    async with test_db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def test_db_session(test_db_setup) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async with get_async_session() as session:
        yield session


# FastAPI test client
@pytest.fixture
def test_client() -> Generator[TestClient, None, None]:
    """Create test client for FastAPI."""
    with TestClient(app) as client:
        yield client


# Mock fixtures
@pytest.fixture
def mock_llm_response():
    """Mock LLM response."""
    return {
        "text": "Это тестовый ответ от LLM",
        "provider": "ollama",
        "model": "llama3.2:3b",
        "tokens_input": 10,
        "tokens_output": 20,
        "latency_ms": 100,
        "metadata": {},
    }


@pytest.fixture
def mock_rag_results():
    """Mock RAG results."""
    return [
        {
            "id": "test_001",
            "content": "Тестовая информация о товаре",
            "score": 0.95,
            "metadata": {"type": "product"},
        },
        {
            "id": "test_002",
            "content": "Тестовый паттерн продаж",
            "score": 0.90,
            "metadata": {"type": "sales_pattern"},
        },
    ]


# Async fixtures
@pytest.fixture
def event_loop():
    """Event loop fixture."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
