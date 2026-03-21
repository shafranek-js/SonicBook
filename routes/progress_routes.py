import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from api_models import ProgressPayload
import progress_service


router = APIRouter()


@router.get("/api/progress/{task_id}", response_model=ProgressPayload)
async def get_progress(task_id: str):
    return progress_service.get_progress(task_id)


@router.get("/api/progress/stream/{task_id}")
async def progress_stream(task_id: str, request: Request):
    async def event_generator():
        last_percent = -1
        last_status = None
        while True:
            if await request.is_disconnected():
                break

            data = progress_service.get_progress(task_id)

            if data.get("percent") != last_percent or data.get("status") != last_status:
                last_percent = data.get("percent", -1)
                last_status = data.get("status")
                yield f"data: {json.dumps(data)}\n\n"

            if data.get("status") in ["success", "error", "not_found", "interrupted"]:
                yield f"data: {json.dumps(data)}\n\n"
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
