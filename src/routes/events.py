import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from src.sse import event_stream, emit_event

router = APIRouter(prefix="/events", tags=["events"])


@router.get("")
async def sse_feed(request: Request, last_event_id: str | None = None):
    queue = asyncio.Queue(maxsize=100)
    raw_id = request.headers.get("last-event-id") or last_event_id
    parsed_id = int(raw_id) if raw_id and raw_id.isdigit() else None
    return StreamingResponse(
        event_stream(queue, parsed_id),
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