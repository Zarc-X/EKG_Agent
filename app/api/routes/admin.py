from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.models import (
    BranchCheckoutRequest,
    BranchCheckoutResponse,
    BranchCreateRequest,
    BranchCreateResponse,
    ChangeExplanationItem,
    ChangeLogItem,
    VersionTreeResponse,
    VersionView,
)
from app.core.workflow import UnifiedWorkflowService

from ..dependencies import get_workflow

router = APIRouter(tags=["admin"])


@router.get("/admin/versions", response_model=list[VersionView])
def list_versions(
    limit: int = 30,
    thread_id: str | None = None,
    branch: str | None = None,
    workflow: UnifiedWorkflowService = Depends(get_workflow),
) -> list[VersionView]:
    records = workflow.list_versions(limit=limit, thread_id=thread_id, branch=branch)
    heads: dict[str, str] = {}
    if thread_id:
        _, heads = workflow.list_version_tree(thread_id=thread_id, limit=limit)

    return [
        VersionView(
            version_id=r.version_id,
            label=r.label,
            created_at=r.created_at,
            metadata=r.metadata,
            parent_version_id=r.parent_version_id,
            thread_id=r.thread_id,
            branch=r.branch,
            is_head=heads.get(r.branch) == r.version_id,
        )
        for r in records
    ]


@router.get("/admin/version-tree", response_model=VersionTreeResponse)
def version_tree(
    thread_id: str = "web-thread",
    limit: int = 200,
    workflow: UnifiedWorkflowService = Depends(get_workflow),
) -> VersionTreeResponse:
    nodes, heads = workflow.list_version_tree(thread_id=thread_id, limit=limit)
    return VersionTreeResponse(
        thread_id=thread_id,
        heads=heads,
        nodes=[
            VersionView(
                version_id=r.version_id,
                label=r.label,
                created_at=r.created_at,
                metadata=r.metadata,
                parent_version_id=r.parent_version_id,
                thread_id=r.thread_id,
                branch=r.branch,
                is_head=heads.get(r.branch) == r.version_id,
            )
            for r in nodes
        ],
    )


@router.post("/admin/branches", response_model=BranchCreateResponse)
def create_branch(
    request: BranchCreateRequest,
    workflow: UnifiedWorkflowService = Depends(get_workflow),
) -> BranchCreateResponse:
    try:
        head = workflow.create_branch(
            thread_id=request.thread_id,
            branch=request.branch,
            from_version_id=request.from_version_id,
            from_branch=request.from_branch,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return BranchCreateResponse(
        status="ok",
        thread_id=request.thread_id,
        branch=request.branch,
        head_version_id=head,
    )


@router.post("/admin/checkout", response_model=BranchCheckoutResponse)
def checkout_branch(
    request: BranchCheckoutRequest,
    workflow: UnifiedWorkflowService = Depends(get_workflow),
) -> BranchCheckoutResponse:
    try:
        head = workflow.checkout_branch(thread_id=request.thread_id, branch=request.branch)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return BranchCheckoutResponse(
        status="ok",
        thread_id=request.thread_id,
        branch=request.branch,
        active_head=head,
    )


@router.post("/admin/rollback/{version_id}")
def rollback(
    version_id: str,
    thread_id: str | None = None,
    branch: str | None = None,
    workflow: UnifiedWorkflowService = Depends(get_workflow),
) -> dict[str, str]:
    try:
        record = workflow.rollback(version_id, thread_id=thread_id, branch=branch)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "status": "ok",
        "rolled_back_to": record.version_id,
        "label": record.label,
        "thread_id": thread_id or record.thread_id,
        "branch": branch or record.branch,
    }


@router.get("/admin/change-logs", response_model=list[ChangeLogItem])
def list_change_logs(
    limit: int = 50,
    thread_id: str | None = None,
    branch: str | None = None,
    workflow: UnifiedWorkflowService = Depends(get_workflow),
) -> list[ChangeLogItem]:
    return workflow.list_change_logs(limit=limit, thread_id=thread_id, branch=branch)


@router.get("/admin/change-explanations", response_model=list[ChangeExplanationItem])
def list_change_explanations(
    limit: int = 50,
    thread_id: str | None = None,
    branch: str | None = None,
    workflow: UnifiedWorkflowService = Depends(get_workflow),
) -> list[ChangeExplanationItem]:
    return workflow.list_change_explanations(limit=limit, thread_id=thread_id, branch=branch)
