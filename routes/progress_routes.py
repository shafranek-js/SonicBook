import asyncio
import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

import progress_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/progress", tags=["progress"])


@router.get("/{task_id}")
async def get_progress(task_id: str):
    return progress_service.get_progress(task_id)


@router.get("/stream/{task_id}")
async def progress_stream(task_id: str, request: Request):
    async def event_generator():
        last_payload = None
        try:
            while True:
                if await request.is_disconnected():
                    break

                data = progress_service.get_progress(task_id)
                payload = json.dumps(data, ensure_ascii=False, sort_keys=True)

                if payload != last_payload:
                    last_payload = payload
                    yield f"data: {payload}\n\n"

                if data.get("status") in ["success", "error", "not_found"]:
                    break

                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            logger.debug("SSE progress stream cancelled for task %s", task_id)
        except (ConnectionResetError, BrokenPipeError, RuntimeError):
            logger.debug("SSE progress stream disconnected for task %s", task_id)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
