import asyncio
import json
from collections import deque
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

# API Gateway kills long-lived connections after ~30s regardless of activity,
# so EventSource reconnects periodically. History + Last-Event-ID replay let
# reconnecting clients pick up any events they missed during the gap.
HISTORY_SIZE = 200
KEEPALIVE_SECONDS = 15

_subscribers: list[asyncio.Queue] = []
_history: deque[tuple[int, dict]] = deque(maxlen=HISTORY_SIZE)
_next_id = 0


def get_subscribers():
    return _subscribers


async def event_stream(queue: asyncio.Queue, last_event_id: Optional[int] = None) -> AsyncGenerator[str, None]:
    if last_event_id is not None:
        for event_id, data in _history:
            if event_id > last_event_id:
                yield f"id: {event_id}\ndata: {json.dumps(data)}\n\n"

    _subscribers.append(queue)
    try:
        while True:
            try:
                event_id, data = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_SECONDS)
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
                continue
            yield f"id: {event_id}\ndata: {json.dumps(data)}\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        _subscribers.remove(queue)


def emit_event(event_type: str, payload: dict):
    global _next_id
    _next_id += 1
    event_id = _next_id
    event = {
        "event": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": payload,
    }
    _history.append((event_id, event))
    dead = []
    for q in _subscribers:
        try:
            q.put_nowait((event_id, event))
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        try:
            _subscribers.remove(q)
        except ValueError:
            pass