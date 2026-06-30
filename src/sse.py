import asyncio
import json
from datetime import datetime, timezone
from typing import AsyncGenerator

_subscribers: list[asyncio.Queue] = []


def get_subscribers():
    return _subscribers


async def event_stream(queue: asyncio.Queue) -> AsyncGenerator[str, None]:
    _subscribers.append(queue)
    try:
        while True:
            data = await queue.get()
            yield f"data: {json.dumps(data)}\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        _subscribers.remove(queue)


def emit_event(event_type: str, payload: dict):
    event = {
        "event": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": payload,
    }
    dead = []
    for q in _subscribers:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        try:
            _subscribers.remove(q)
        except ValueError:
            pass