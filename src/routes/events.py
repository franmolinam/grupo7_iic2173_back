import asyncio
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from src.sse import event_stream, emit_event

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


class EmitPayload(BaseModel):
    event: str
    data: dict


@router.post("/emit")
async def internal_emit(payload: EmitPayload):
    emit_event(payload.event, payload.data)
    return {"ok": True}