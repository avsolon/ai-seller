"""SSE event bus for widget sessions (doc 13).

In-memory per-session queues: the browser opens GET /events first, then POSTs a
message; the endpoint pushes typed events back over the SSE stream. For multiple
uvicorn workers switch this to Redis pub/sub.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Dict, Optional, Tuple

_QUEUES: Dict[str, asyncio.Queue] = {}
_QUEUE_MAXSIZE = 200


def _queue(session_id: str) -> asyncio.Queue:
    if session_id not in _QUEUES:
        _QUEUES[session_id] = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
    return _QUEUES[session_id]


async def push_event(session_id: str, event: str, data: dict) -> None:
    try:
        _queue(session_id).put_nowait((event, json.dumps(data, ensure_ascii=False)))
    except asyncio.QueueFull:
        pass


async def next_event(session_id: str, timeout: float = 15.0) -> Optional[Tuple[str, str]]:
    try:
        return await asyncio.wait_for(_queue(session_id).get(), timeout=timeout)
    except asyncio.TimeoutError:
        return None


def split_text(text: str, max_len: int = 64) -> list:
    """Split the reply into SSE message_delta chunks by sentences/words."""
    sentences = re.split(r"(?<=[.!?])\s+|\n", text.strip())
    chunks: list = []
    current = ""
    for part in sentences:
        part = part.strip()
        if not part:
            continue
        if len(current) + len(part) + 1 > max_len and current:
            chunks.append(current)
            current = part
        else:
            current = (current + " " + part).strip()
        while len(current) > max_len:
            chunks.append(current[:max_len])
            current = current[max_len:]
    if current:
        chunks.append(current)
    return chunks or [text.strip()]
