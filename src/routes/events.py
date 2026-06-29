import asyncio
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from src.sse import event_stream

router = APIRouter(prefix="/events", tags=["events"])


@router.get("")
async def sse_feed():
    queue = asyncio.Queue(maxsize=100)
    return StreamingResponse(
        event_stream(queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )