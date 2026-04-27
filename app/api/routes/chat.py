from __future__ import annotations

from collections.abc import Iterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.core.events import format_sse_event
from app.core.models import ChatRequest, ChatResponse
from app.core.workflow import UnifiedWorkflowService

from ..dependencies import get_workflow

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(
    request_body: ChatRequest,
    workflow: UnifiedWorkflowService = Depends(get_workflow),
) -> ChatResponse:
    return workflow.process_chat(request_body)


@router.post("/chat/stream")
def chat_stream(
    request_body: ChatRequest,
    workflow: UnifiedWorkflowService = Depends(get_workflow),
) -> StreamingResponse:
    def event_stream() -> Iterator[str]:
        yield format_sse_event("stage", {"name": "graph_rag", "status": "started"})
        response = workflow.process_chat(request_body)
        yield format_sse_event("stage", {"name": "graph_rag", "status": "completed"})
        yield format_sse_event("result", response.model_dump())
        yield format_sse_event("complete", {"status": "done"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
