"""Channel messaging application service tests (doc 12)."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.channels import IncomingMessage, MessageApplicationService, MessageChannel
from app.infrastructure.database.base import Base
from app.infrastructure.database.models.conversation import Message
from app.infrastructure.database.models.customer import Customer, CustomerExternalID
from app.infrastructure.database.models.manager_task import ManagerTask


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


def incoming(text: str, msg_id: str = "100", chat: str = "12345", user: str = "999"):
    return IncomingMessage(
        channel=MessageChannel.TELEGRAM,
        external_user_id=user,
        external_conversation_id=chat,
        external_message_id=msg_id,
        text=text,
    )


async def count_messages(db, channel: str = "telegram", external: str | None = None):
    query = select(func.count()).select_from(Message).where(Message.channel == channel)
    if external is not None:
        query = query.where(Message.external_message_id == external)
    return (await db.execute(query)).scalar_one()


class TestMessageApplicationService:
    async def test_handle_creates_customer_conversation_and_messages(self, db_session):
        async def agent(db, conversation, text):
            return "Подскажите марку автомобиля."

        service = MessageApplicationService(agent=agent)
        result = await service.handle(db_session, incoming("Привет"))
        assert result.text == "Подскажите марку автомобиля."

        customers = (
            await db_session.execute(select(Customer))
        ).scalars().all()
        assert len(customers) == 1
        ext = (
            await db_session.execute(select(CustomerExternalID))
        ).scalars().all()
        assert ext and ext[0].external_id == "999"
        assert await count_messages(db_session) == 2  # customer + agent

    async def test_idempotency_ignores_duplicate(self, db_session):
        async def agent(db, conversation, text):
            return "ok"

        service = MessageApplicationService(agent=agent)
        first = await service.handle(db_session, incoming("Привет", msg_id="200"))
        assert first.text == "ok"

        second = await service.handle(db_session, incoming("Привет", msg_id="200"))
        assert second.text == ""
        assert await count_messages(db_session) == 2

    async def test_reuses_active_conversation(self, db_session):
        async def agent(db, conversation, text):
            return f"conv={conversation.id}"

        service = MessageApplicationService(agent=agent)
        r1 = await service.handle(db_session, incoming("Привет", msg_id="1", chat="42"))
        r2 = await service.handle(db_session, incoming("Дорого", msg_id="2", chat="42"))
        assert r1.metadata["conversation_id"] == r2.metadata["conversation_id"]
        assert r1.text == r2.text

    async def test_handoff_creates_manager_task(self, db_session):
        async def agent(db, conversation, text):
            conversation.status = "handed_off"
            return "Передаю менеджеру."

        service = MessageApplicationService(agent=agent)
        result = await service.handle(db_session, incoming("/manager"))
        assert result.text == "Передаю менеджеру."
        tasks = (
            await db_session.execute(select(ManagerTask))
        ).scalars().all()
        assert len(tasks) == 1
        assert tasks[0].type == "handoff"
        assert tasks[0].status == "open"
