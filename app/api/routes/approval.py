from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.models import ApprovalDecisionRequest, ApprovalDetailResponse, ApprovalTicket, ChatResponse
from app.core.workflow import UnifiedWorkflowService

from ..dependencies import get_workflow

router = APIRouter(tags=["approval"])


@router.get("/approvals", response_model=list[ApprovalTicket])
def list_approvals(
    status: str | None = None,
    workflow: UnifiedWorkflowService = Depends(get_workflow),
) -> list[ApprovalTicket]:
    return workflow.list_approvals(status=status)


@router.get("/approvals/{ticket_id}", response_model=ApprovalDetailResponse)
def get_approval_detail(
    ticket_id: str,
    workflow: UnifiedWorkflowService = Depends(get_workflow),
) -> ApprovalDetailResponse:
    try:
        ticket, payload, approval_copilot = workflow.get_approval_detail(ticket_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ApprovalDetailResponse(
        ticket=ticket,
        payload=payload,
        approval_copilot=approval_copilot,
    )


@router.post("/approvals/{ticket_id}/decision", response_model=ChatResponse)
def decide_approval(
    ticket_id: str,
    decision: ApprovalDecisionRequest,
    workflow: UnifiedWorkflowService = Depends(get_workflow),
) -> ChatResponse:
    approval_copilot = None
    try:
        _, _, approval_copilot = workflow.get_approval_detail(ticket_id)
    except ValueError:
        approval_copilot = None

    try:
        ticket = workflow.approval.decide(
            ticket_id=ticket_id,
            approved=decision.approved,
            approver=decision.approver,
            reason=decision.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not decision.approved:
        return ChatResponse(
            status="blocked",
            answer="审批已拒绝，操作不会执行。",
            trace_id=ticket.trace_id,
            approval_ticket_id=ticket.ticket_id,
            approval_copilot=approval_copilot,
        )

    try:
        return workflow.execute_approved(ticket_id=ticket_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
