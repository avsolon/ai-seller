"""Widget SSE helpers tests."""

import asyncio

from app.api.widget_events import next_event, push_event, split_text


def test_split_text_by_sentences():
    text = "Подберём. Подскажите год Camry? Галоген или ксенон?"
    chunks = split_text(text, max_len=40)
    assert chunks
    joined = "".join(chunks)
    # joining strips inter-chunk spaces, compare without whitespace
    assert "".join(text.split()) == "".join(joined.split())
    assert all(len(c) <= 40 or " " not in c for c in chunks)


class TestEventBus:
    def test_push_and_consume(self):
        async def run():
            await push_event("sess-1", "message_delta", {"text": "Привет"})
            event, data = await next_event("sess-1", timeout=1.0)
            assert event == "message_delta"
            assert data == '{"text": "Привет"}'

        asyncio.run(run())

    def test_timeout_returns_none(self):
        async def run():
            assert await next_event("empty-sess", timeout=0.1) is None

        asyncio.run(run())
