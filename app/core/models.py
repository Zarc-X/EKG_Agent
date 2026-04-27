from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    user_id: str = Field(min_length=1)
    thread_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    auto_approve: bool = False
    branch: str | None = None


class EvidenceItem(BaseModel):
    node_id: str
    title: str
    score: float
    relation_summary: str


class ApprovalPolicyMapping(BaseModel):
    policy: str
    status: str
    evidence: str


class ApprovalCopilotSummary(BaseModel):
    recommendation: str
    confidence: float | None = None
    final_decision: str
    risk_level: str
    rationale: str = ""
    risk_points: list[str] = Field(default_factory=list)
    suggested_actions: list[str] = Field(default_factory=list)
    approver_checklist: list[str] = Field(default_factory=list)
    policy_mappings: list[ApprovalPolicyMapping] = Field(default_factory=list)


class ChatResponse(BaseModel):
    status: Literal["completed", "pending_approval", "blocked", "error"]
    answer: str
    trace_id: str | None = None
    approval_ticket_id: str | None = None
    generated_sql: str | None = None
    generated_python_code: str | None = None
    security: dict[str, Any] | None = None
    approval_copilot: ApprovalCopilotSummary | None = None
    evidence: list[EvidenceItem] = Field(default_factory=list)
    execution: dict[str, Any] | None = None


class ApprovalTicket(BaseModel):
    ticket_id: str
    trace_id: str
    status: Literal["pending", "approved", "rejected", "executed", "failed"]
    summary: str
    created_at: datetime
    updated_at: datetime
    requester: str
    approver: str | None = None
    reason: str | None = None


class ApprovalDetailResponse(BaseModel):
    ticket: ApprovalTicket
    payload: dict[str, Any] = Field(default_factory=dict)
    approval_copilot: ApprovalCopilotSummary | None = None


class ApprovalDecisionRequest(BaseModel):
    approved: bool
    approver: str = Field(min_length=1)
    reason: str | None = None


class VersionView(BaseModel):
    version_id: str
    label: str
    created_at: datetime
    metadata: dict[str, Any]
    parent_version_id: str | None = None
    thread_id: str = "global"
    branch: str = "main"
    is_head: bool = False


class VersionTreeResponse(BaseModel):
    thread_id: str
    nodes: list[VersionView]
    heads: dict[str, str]


class BranchCreateRequest(BaseModel):
    thread_id: str = Field(min_length=1)
    branch: str = Field(min_length=1)
    from_version_id: str | None = None
    from_branch: str = "main"


class BranchCreateResponse(BaseModel):
    status: str
    thread_id: str
    branch: str
    head_version_id: str | None = None


class BranchCheckoutRequest(BaseModel):
    thread_id: str = Field(min_length=1)
    branch: str = Field(min_length=1)


class BranchCheckoutResponse(BaseModel):
    status: str
    thread_id: str
    branch: str
    active_head: str | None = None


class ChangeLogItem(BaseModel):
    version_id: str
    parent_version_id: str | None = None
    label: str
    created_at: datetime
    thread_id: str
    branch: str
    trace_id: str | None = None
    user_id: str | None = None
    operation_type: str
    summary: str
    sql: str
    params: list[Any] = Field(default_factory=list)
    touched_tables: list[str] = Field(default_factory=list)
    rowcount: int | None = None


class KnowledgeSearchResponse(BaseModel):
    query: str
    context: str
    evidence: list[EvidenceItem]
