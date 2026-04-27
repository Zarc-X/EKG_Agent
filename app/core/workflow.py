from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any

from app.codegen import ComponentCodeGenerator, GeneratedAction
from app.db import ComponentRepository, SqlSandboxPolicy, SqliteVersionStore, VersionRecord
from app.knowledge import GraphRAGResult, GraphRAGService

from .approval import ApprovalService
from .models import (
    ApprovalCopilotSummary,
    ApprovalPolicyMapping,
    ApprovalTicket,
    ChangeExplanationItem,
    ChangeLogItem,
    ChatRequest,
    ChatResponse,
    EvidenceItem,
)
from .security_runtime import SecurityBundle


@dataclass(slots=True)
class PendingExecution:
    ticket_id: str
    action: GeneratedAction
    graph_result: GraphRAGResult
    request: ChatRequest
    pre_result: Any


class UnifiedWorkflowService:
    _PROTECTED_TABLES = {"components", "inventory", "bom", "supplier_pricing"}
    _RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3, "unknown": 4}

    def __init__(
        self,
        *,
        graph_rag: GraphRAGService,
        codegen: ComponentCodeGenerator,
        repo: ComponentRepository,
        versions: SqliteVersionStore,
        approval: ApprovalService,
        security: SecurityBundle,
        sql_sandbox: SqlSandboxPolicy | None = None,
        sandbox_enabled: bool = True,
        top_k: int = 5,
    ) -> None:
        self.graph_rag = graph_rag
        self.codegen = codegen
        self.repo = repo
        self.versions = versions
        self.approval = approval
        self.security = security
        self.sql_sandbox = sql_sandbox or SqlSandboxPolicy()
        self.sandbox_enabled = sandbox_enabled
        self.top_k = top_k

        self._pending: dict[str, PendingExecution] = {}
        self._active_branch_by_thread: dict[str, str] = {}

    def process_chat(self, request: ChatRequest) -> ChatResponse:
        if request.branch:
            self._active_branch_by_thread[request.thread_id] = request.branch

        graph_result = self.graph_rag.retrieve(request.message, top_k=self.top_k, hops=1)
        action = self.codegen.generate(user_query=request.message, graph_context=graph_result.context)

        plan, context = self._build_security_objects(request=request, action=action)
        pre = self.security.service.pre_operation(plan, context)
        approval_copilot = self._build_approval_copilot(
            pre=pre,
            request=request,
            action=action,
        )
        approval_copilot_payload = approval_copilot.model_dump()

        if pre.final_decision == self.security.Decision.BLOCK:
            return ChatResponse(
                status="blocked",
                answer="安全策略拒绝了本次操作。",
                trace_id=pre.trace_id,
                generated_sql=action.sql,
                generated_python_code=action.python_code,
                security={
                    "pre": pre.to_dict(),
                    "approval_copilot": approval_copilot_payload,
                },
                approval_copilot=approval_copilot,
                evidence=self._to_evidence_items(graph_result),
            )

        if pre.final_decision == self.security.Decision.REQUIRE_HUMAN and not request.auto_approve:
            ticket = self.approval.create_ticket(
                trace_id=pre.trace_id,
                requester=request.user_id,
                summary=action.summary,
                payload={
                    "action": {
                        "operation_type": action.operation_type,
                        "sql": action.sql,
                        "params": list(action.params),
                        "requires_write": action.requires_write,
                        "estimated_rows": action.estimated_rows,
                        "summary": action.summary,
                        "python_code": action.python_code,
                    },
                    "request": request.model_dump(),
                    "graph_context": graph_result.context,
                    "evidence": [e.__dict__ for e in graph_result.evidence],
                    "pre": pre.to_dict(),
                    "approval_copilot": approval_copilot_payload,
                },
            )
            self._pending[ticket.ticket_id] = PendingExecution(
                ticket_id=ticket.ticket_id,
                action=action,
                graph_result=graph_result,
                request=request,
                pre_result=pre,
            )
            return ChatResponse(
                status="pending_approval",
                answer="该操作风险较高，已创建审批单，等待人工确认。",
                trace_id=pre.trace_id,
                approval_ticket_id=ticket.ticket_id,
                generated_sql=action.sql,
                generated_python_code=action.python_code,
                security={
                    "pre": pre.to_dict(),
                    "approval_copilot": approval_copilot_payload,
                },
                approval_copilot=approval_copilot,
                evidence=self._to_evidence_items(graph_result),
            )

        return self._execute_prechecked(request, action, graph_result, pre)

    def execute_approved(self, *, ticket_id: str) -> ChatResponse:
        pending = self._pending.get(ticket_id)
        if pending is None:
            raise ValueError(f"pending execution not found for ticket: {ticket_id}")

        try:
            response = self._execute_prechecked(
                pending.request,
                pending.action,
                pending.graph_result,
                pending.pre_result,
            )
            if response.approval_copilot is None:
                response.approval_copilot = self._build_approval_copilot(
                    pre=pending.pre_result,
                    request=pending.request,
                    action=pending.action,
                )
            if response.status == "completed":
                self.approval.mark_executed(ticket_id)
            else:
                self.approval.mark_failed(ticket_id, response.answer)
            return response
        finally:
            self._pending.pop(ticket_id, None)

    def _execute_prechecked(
        self,
        request: ChatRequest,
        action: GeneratedAction,
        graph_result: GraphRAGResult,
        pre: Any,
    ) -> ChatResponse:
        current_branch = self._active_branch(request.thread_id)

        sandbox_validation = self.sql_sandbox.validate(
            action.sql,
            allowed_tables={t.lower() for t in self.repo.list_tables()},
        )
        sandbox_reason = sandbox_validation.reason if self.sandbox_enabled else "sandbox disabled"
        sandbox_tables = sandbox_validation.touched_tables if self.sandbox_enabled else []
        if self.sandbox_enabled and not sandbox_validation.allowed:
            return ChatResponse(
                status="blocked",
                answer=f"沙箱策略拒绝执行: {sandbox_validation.reason}",
                trace_id=pre.trace_id,
                generated_sql=action.sql,
                generated_python_code=action.python_code,
                security={
                    "pre": pre.to_dict(),
                    "sandbox": {
                        "allowed": False,
                        "reason": sandbox_validation.reason,
                        "statements": sandbox_validation.statements,
                        "touched_tables": sandbox_validation.touched_tables,
                    },
                },
                evidence=self._to_evidence_items(graph_result),
            )

        sandbox_result: dict[str, Any] | None = None
        if self.sandbox_enabled:
            try:
                sandbox_result = self.repo.simulate_sql(action.sql, action.params)
            except Exception as exc:
                return ChatResponse(
                    status="blocked",
                    answer=f"沙箱干跑失败: {exc}",
                    trace_id=pre.trace_id,
                    generated_sql=action.sql,
                    generated_python_code=action.python_code,
                    security={
                        "pre": pre.to_dict(),
                        "sandbox": {
                            "allowed": False,
                            "reason": str(exc),
                            "statements": sandbox_validation.statements,
                            "touched_tables": sandbox_validation.touched_tables,
                        },
                    },
                    evidence=self._to_evidence_items(graph_result),
                )

        plan, context = self._build_security_objects(request=request, action=action)

        during = self.security.service.during_operation(
            plan=plan,
            context=context,
            trace_id=pre.trace_id,
            capability=pre.capability_token,
        )

        if not during.allowed:
            return ChatResponse(
                status="blocked",
                answer=f"执行中安全检查未通过: {during.reason}",
                trace_id=pre.trace_id,
                generated_sql=action.sql,
                generated_python_code=action.python_code,
                security={
                    "pre": pre.to_dict(),
                    "sandbox": {
                        "allowed": self.sandbox_enabled,
                        "reason": sandbox_reason,
                        "touched_tables": sandbox_tables,
                        "preview": sandbox_result,
                    },
                    "during": during.to_dict(),
                },
                evidence=self._to_evidence_items(graph_result),
            )

        before_version: VersionRecord | None = None
        after_version: VersionRecord | None = None
        change_log: dict[str, Any] | None = None
        ontology_update: dict[str, Any] | None = None

        try:
            if action.requires_write:
                before_version = self.versions.create_version(
                    label=f"before:{action.summary}",
                    metadata=self._build_version_metadata(
                        request=request,
                        action=action,
                        trace_id=pre.trace_id,
                        branch=current_branch,
                        phase="before",
                        touched_tables=sandbox_tables,
                    ),
                    thread_id=request.thread_id,
                    branch=current_branch,
                )

            execution = self.repo.execute_sql(action.sql, action.params)

            if action.requires_write:
                change_log = self._build_change_log(
                    action=action,
                    execution=execution,
                    touched_tables=sandbox_tables,
                )
                after_version = self.versions.create_version(
                    label=f"after:{action.summary}",
                    metadata=self._build_version_metadata(
                        request=request,
                        action=action,
                        trace_id=pre.trace_id,
                        branch=current_branch,
                        phase="after",
                        touched_tables=sandbox_tables,
                        change_log=change_log,
                    ),
                    thread_id=request.thread_id,
                    branch=current_branch,
                    parent_version_id=before_version.version_id if before_version else None,
                )
                try:
                    ontology_update = self.graph_rag.apply_ontology_incremental_update(
                        thread_id=request.thread_id,
                        branch=current_branch,
                        user_id=request.user_id,
                        trace_id=pre.trace_id,
                        change_log=change_log,
                        version_id=after_version.version_id if after_version else None,
                        parent_version_id=before_version.version_id if before_version else None,
                        recorded_at=datetime.now(timezone.utc).isoformat(),
                    )
                except Exception as ontology_exc:
                    ontology_update = {
                        "status": "failed",
                        "reason": str(ontology_exc),
                    }

            sec_result = self.security.SecurityExecutionResult(
                success=True,
                message="ok",
                metadata={
                    "version_id": after_version.version_id if after_version else None,
                    "parent_version_id": before_version.version_id if before_version else None,
                    "rowcount": execution.get("rowcount", 0),
                    "ontology_update": ontology_update,
                },
                raw_result=execution,
            )
            post = self.security.service.post_operation(
                plan=plan,
                context=context,
                trace_id=pre.trace_id,
                execution_result=sec_result,
            )

            answer = self._format_answer(action=action, execution=execution)
            return ChatResponse(
                status="completed",
                answer=answer,
                trace_id=pre.trace_id,
                generated_sql=action.sql,
                generated_python_code=action.python_code,
                security={
                    "pre": pre.to_dict(),
                    "sandbox": {
                        "allowed": self.sandbox_enabled,
                        "reason": sandbox_reason,
                        "touched_tables": sandbox_tables,
                        "preview": sandbox_result,
                    },
                    "during": during.to_dict(),
                    "post": post.to_dict(),
                    "change_log": change_log,
                    "ontology_update": ontology_update,
                },
                evidence=self._to_evidence_items(graph_result),
                execution=execution,
            )
        except Exception as exc:
            if before_version is not None:
                self.versions.rollback(
                    before_version.version_id,
                    thread_id=request.thread_id,
                    branch=current_branch,
                )

            sec_result = self.security.SecurityExecutionResult(
                success=False,
                message=str(exc),
                metadata={
                    "version_id": None,
                    "parent_version_id": before_version.version_id if before_version else None,
                    "ontology_update": ontology_update,
                },
                raw_result={"error": str(exc)},
            )
            post = self.security.service.post_operation(
                plan=plan,
                context=context,
                trace_id=pre.trace_id,
                execution_result=sec_result,
            )

            return ChatResponse(
                status="error",
                answer=f"执行失败: {exc}",
                trace_id=pre.trace_id,
                generated_sql=action.sql,
                generated_python_code=action.python_code,
                security={
                    "pre": pre.to_dict(),
                    "sandbox": {
                        "allowed": self.sandbox_enabled,
                        "reason": sandbox_reason,
                        "touched_tables": sandbox_tables,
                        "preview": sandbox_result,
                    },
                    "during": during.to_dict(),
                    "post": post.to_dict(),
                    "change_log": change_log,
                    "ontology_update": ontology_update,
                },
                evidence=self._to_evidence_items(graph_result),
            )

    def _build_security_objects(self, *, request: ChatRequest, action: GeneratedAction) -> tuple[Any, Any]:
        op_kind = self.security.OperationKind.READ_QUERY
        if action.operation_type == "write":
            op_kind = self.security.OperationKind.WRITE_QUERY

        tables = self._extract_tables(action.sql)

        plan = self.security.OperationPlan.new(
            operation_kind=op_kind,
            tool_name="generated_sql_executor",
            raw_payload=action.sql,
            statements=[action.sql],
            touched_tables=tables,
            estimated_rows=action.estimated_rows,
            requires_write=action.requires_write,
            metadata={"summary": action.summary},
        )

        context = self.security.OperationContext(
            user_id=request.user_id,
            thread_id=request.thread_id,
            source_repo="ekg_agent_refactor",
            actor_role="agent",
            metadata={
                "user_message": request.message,
                "branch": self._active_branch(request.thread_id),
            },
        )
        return plan, context

    def _extract_tables(self, sql: str) -> list[str]:
        patterns = [
            r"\bfrom\s+([a-zA-Z_][\w\.]*)",
            r"\bjoin\s+([a-zA-Z_][\w\.]*)",
            r"\bupdate\s+([a-zA-Z_][\w\.]*)",
            r"\binto\s+([a-zA-Z_][\w\.]*)",
            r"\bdelete\s+from\s+([a-zA-Z_][\w\.]*)",
        ]
        out: set[str] = set()
        for p in patterns:
            for m in re.finditer(p, sql, flags=re.I):
                out.add(m.group(1).lower())
        return sorted(out)

    def _to_evidence_items(self, graph_result: GraphRAGResult) -> list[EvidenceItem]:
        return [
            EvidenceItem(
                node_id=e.node_id,
                title=e.title,
                score=e.score,
                relation_summary=e.relation_summary,
            )
            for e in graph_result.evidence
        ]

    def _format_answer(self, *, action: GeneratedAction, execution: dict[str, Any]) -> str:
        if action.requires_write:
            return f"已完成写操作：{action.summary}。影响行数约 {execution.get('rowcount', 0)}。"

        rows = execution.get("rows", [])
        if not rows:
            return "查询完成，但未命中数据。"

        preview = rows[:3]
        return f"查询完成，返回 {len(rows)} 行数据，示例: {preview}"

    def list_versions(
        self,
        limit: int = 50,
        *,
        thread_id: str | None = None,
        branch: str | None = None,
    ) -> list[VersionRecord]:
        return self.versions.list_versions(limit=limit, thread_id=thread_id, branch=branch)

    def list_version_tree(self, *, thread_id: str, limit: int = 200) -> tuple[list[VersionRecord], dict[str, str]]:
        return self.versions.list_tree(thread_id=thread_id, limit=limit)

    def rollback(
        self,
        version_id: str,
        *,
        thread_id: str | None = None,
        branch: str | None = None,
    ) -> VersionRecord:
        return self.versions.rollback(version_id, thread_id=thread_id, branch=branch)

    def create_branch(
        self,
        *,
        thread_id: str,
        branch: str,
        from_version_id: str | None = None,
        from_branch: str = "main",
    ) -> str | None:
        return self.versions.create_branch(
            thread_id=thread_id,
            branch=branch,
            from_version_id=from_version_id,
            from_branch=from_branch,
        )

    def checkout_branch(self, *, thread_id: str, branch: str) -> str | None:
        head = self.versions.get_head(thread_id=thread_id, branch=branch)
        self._active_branch_by_thread[thread_id] = branch
        if head:
            self.versions.rollback(head, thread_id=thread_id, branch=branch)
        return head

    def get_active_branch(self, *, thread_id: str) -> str:
        return self._active_branch(thread_id)

    def list_approvals(self, status: str | None = None) -> list[ApprovalTicket]:
        return self.approval.list_tickets(status=status)

    def get_approval_detail(self, ticket_id: str) -> tuple[ApprovalTicket, dict[str, Any], ApprovalCopilotSummary | None]:
        ticket = self.approval.get_ticket(ticket_id)
        if ticket is None:
            raise ValueError(f"ticket not found: {ticket_id}")

        payload = self.approval.get_payload(ticket_id) or {}
        approval_copilot: ApprovalCopilotSummary | None = None
        raw = payload.get("approval_copilot")
        if isinstance(raw, dict):
            try:
                approval_copilot = ApprovalCopilotSummary.model_validate(raw)
            except Exception:
                approval_copilot = None

        return ticket, payload, approval_copilot

    def list_change_logs(
        self,
        limit: int = 50,
        *,
        thread_id: str | None = None,
        branch: str | None = None,
    ) -> list[ChangeLogItem]:
        fetch_limit = max(limit * 4, limit)
        records = self.versions.list_versions(limit=fetch_limit, thread_id=thread_id, branch=branch)

        out: list[ChangeLogItem] = []
        for r in records:
            metadata = r.metadata if isinstance(r.metadata, dict) else {}
            change_log = metadata.get("change_log")
            if not isinstance(change_log, dict):
                continue

            params = change_log.get("params")
            if not isinstance(params, list):
                params = []

            touched_tables = change_log.get("touched_tables")
            if not isinstance(touched_tables, list):
                touched_tables = []

            rowcount = change_log.get("rowcount")
            if not isinstance(rowcount, int):
                rowcount = None

            out.append(
                ChangeLogItem(
                    version_id=r.version_id,
                    parent_version_id=r.parent_version_id,
                    label=r.label,
                    created_at=datetime.fromisoformat(r.created_at),
                    thread_id=r.thread_id,
                    branch=r.branch,
                    trace_id=metadata.get("trace_id"),
                    user_id=metadata.get("user_id"),
                    operation_type=str(change_log.get("operation_type") or "write"),
                    summary=str(change_log.get("summary") or r.label),
                    sql=str(change_log.get("sql") or ""),
                    params=params,
                    touched_tables=[str(t) for t in touched_tables],
                    rowcount=rowcount,
                )
            )

            if len(out) >= limit:
                break

        return out

    def list_change_explanations(
        self,
        limit: int = 50,
        *,
        thread_id: str | None = None,
        branch: str | None = None,
    ) -> list[ChangeExplanationItem]:
        logs = self.list_change_logs(limit=limit, thread_id=thread_id, branch=branch)
        return [self._explain_change_log(item) for item in logs]

    def _active_branch(self, thread_id: str) -> str:
        return self._active_branch_by_thread.get(thread_id, "main")

    def _build_version_metadata(
        self,
        *,
        request: ChatRequest,
        action: GeneratedAction,
        trace_id: str,
        branch: str,
        phase: str,
        touched_tables: list[str],
        change_log: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "thread_id": request.thread_id,
            "user_id": request.user_id,
            "branch": branch,
            "phase": phase,
            "trace_id": trace_id,
            "operation_type": action.operation_type,
            "operation_summary": action.summary,
            "touched_tables": list(touched_tables),
            "request_message": request.message,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        if change_log is not None:
            metadata["change_log"] = change_log
        return metadata

    def _build_change_log(
        self,
        *,
        action: GeneratedAction,
        execution: dict[str, Any],
        touched_tables: list[str],
    ) -> dict[str, Any]:
        sql_text = (action.sql or "").strip()
        if len(sql_text) > 3000:
            sql_text = f"{sql_text[:3000]}..."

        return {
            "operation_type": action.operation_type,
            "summary": action.summary,
            "sql": sql_text,
            "params": self._normalize_params(action.params),
            "touched_tables": list(touched_tables or self._extract_tables(action.sql)),
            "rowcount": execution.get("rowcount"),
        }

    def _normalize_params(self, params: tuple[Any, ...] | list[Any]) -> list[Any]:
        out: list[Any] = []
        for item in list(params):
            if isinstance(item, (str, int, float, bool)) or item is None:
                out.append(item)
            else:
                out.append(str(item))
        return out

    def _explain_change_log(self, item: ChangeLogItem) -> ChangeExplanationItem:
        touched = [str(t).lower() for t in item.touched_tables]
        sql_text = (item.sql or "").lower()

        risk_level = "low" if item.operation_type != "write" else "medium"
        reasons: list[str] = []

        if item.operation_type == "write":
            reasons.append("写操作默认需要更严格复核")

        protected_hits = sorted({t for t in touched if t in self._PROTECTED_TABLES})
        if protected_hits:
            risk_level = self._raise_risk(risk_level, "high")
            reasons.append(f"触及核心业务表: {', '.join(protected_hits)}")

        if item.rowcount is None and item.operation_type == "write":
            risk_level = self._raise_risk(risk_level, "high")
            reasons.append("影响行数未知")
        elif isinstance(item.rowcount, int):
            if item.rowcount >= 5000:
                risk_level = self._raise_risk(risk_level, "critical")
                reasons.append(f"影响行数较大: {item.rowcount}")
            elif item.rowcount >= 1000:
                risk_level = self._raise_risk(risk_level, "high")
                reasons.append(f"影响行数偏大: {item.rowcount}")
            elif item.rowcount >= 200:
                risk_level = self._raise_risk(risk_level, "medium")
                reasons.append(f"影响行数中等: {item.rowcount}")

        if re.search(r"\b(update|delete)\b", sql_text) and not re.search(r"\bwhere\b", sql_text):
            risk_level = "critical"
            reasons.append("检测到无 WHERE 条件的 UPDATE/DELETE")

        if re.search(r"\b(drop|truncate)\b", sql_text):
            risk_level = "critical"
            reasons.append("检测到破坏性关键词 DROP/TRUNCATE")

        impact_scope: list[str] = []
        if touched:
            impact_scope.append(f"触表范围: {', '.join(touched)}")
        else:
            impact_scope.append("触表范围: 未解析到明确表名")

        if item.rowcount is None:
            impact_scope.append("影响行数: 未知")
        else:
            impact_scope.append(f"影响行数: {item.rowcount}")

        impact_scope.append(f"操作类型: {item.operation_type}")
        if item.trace_id:
            impact_scope.append(f"审计追踪: {item.trace_id}")

        risk_cn = {
            "low": "低",
            "medium": "中",
            "high": "高",
            "critical": "严重",
            "unknown": "未知",
        }.get(risk_level, "未知")

        reason_text = "；".join(reasons[:2]) if reasons else "未检测到显著风险信号"
        management_summary = (
            f"变更“{item.summary}”已记录。分支 {item.branch} 的风险等级为{risk_cn}，"
            f"{reason_text}。"
        )

        if risk_level in {"high", "critical"}:
            if item.parent_version_id:
                rollback_recommendation = (
                    f"建议优先冻结后续写入并进行抽样核验，若异常可回滚到父版本 {item.parent_version_id}。"
                )
            else:
                rollback_recommendation = "建议立即创建修复版本并执行人工复核流程。"
        elif risk_level == "medium":
            rollback_recommendation = "建议在发布窗口前完成数据抽样核验，必要时回滚到父版本。"
        elif risk_level == "low":
            rollback_recommendation = "建议继续观察并保留当前版本快照，通常无需立即回滚。"
        else:
            rollback_recommendation = "建议补充影响评估信息后再决定是否回滚。"

        checks = [
            "核对变更摘要与业务需求是否一致。",
            "核对触表范围是否符合预期。",
            "复核审计 trace 与审批记录是否完整。",
        ]
        if item.rowcount is None:
            checks.append("补充影响行数评估，避免遗漏大范围变更。")
        if risk_level in {"high", "critical"}:
            checks.append("在下一次写入前完成回滚预案演练。")

        return ChangeExplanationItem(
            version_id=item.version_id,
            parent_version_id=item.parent_version_id,
            label=item.label,
            created_at=item.created_at,
            thread_id=item.thread_id,
            branch=item.branch,
            trace_id=item.trace_id,
            user_id=item.user_id,
            operation_type=item.operation_type,
            summary=item.summary,
            touched_tables=item.touched_tables,
            rowcount=item.rowcount,
            risk_level=risk_level if risk_level in self._RISK_ORDER else "unknown",
            impact_scope=impact_scope,
            management_summary=management_summary,
            rollback_recommendation=rollback_recommendation,
            rollback_target_version_id=item.parent_version_id,
            checks=self._unique_keep_order(checks),
        )

    def _raise_risk(self, current: str, target: str) -> str:
        if self._RISK_ORDER.get(target, -1) > self._RISK_ORDER.get(current, -1):
            return target
        return current

    def _build_approval_copilot(
        self,
        *,
        pre: Any,
        request: ChatRequest,
        action: GeneratedAction,
    ) -> ApprovalCopilotSummary:
        pre_dict = pre.to_dict() if hasattr(pre, "to_dict") else {}
        if not isinstance(pre_dict, dict):
            pre_dict = {}

        rule = pre_dict.get("rule_decision")
        if not isinstance(rule, dict):
            rule = {}

        safe_opinion = pre_dict.get("safe_opinion")
        if not isinstance(safe_opinion, dict):
            safe_opinion = {}

        constraints = rule.get("constraints")
        if not isinstance(constraints, dict):
            constraints = {}

        operation_kind = "write_query" if action.requires_write else "read_query"
        touched_tables = self._extract_tables(action.sql)
        allowed_kinds = {v.lower() for v in self._normalize_str_list(constraints.get("allowed_operation_kinds"))}
        allowed_tables = {v.lower() for v in self._normalize_str_list(constraints.get("allowed_tables"))}

        op_status = "open"
        if allowed_kinds:
            op_status = "covered" if operation_kind in allowed_kinds else "outside_scope"

        outside_tables = [t for t in touched_tables if t.lower() not in allowed_tables] if allowed_tables else []
        table_status = "open"
        if touched_tables:
            table_status = "within_scope" if not outside_tables else "outside_scope"

        max_write_rows = 0
        raw_max_write_rows = constraints.get("max_write_rows")
        if isinstance(raw_max_write_rows, (int, float)):
            max_write_rows = int(raw_max_write_rows)

        row_status = "not_applicable"
        if action.requires_write:
            if max_write_rows > 0 and action.estimated_rows is not None:
                row_status = "within_budget" if action.estimated_rows <= max_write_rows else "exceeds_budget"
            elif max_write_rows > 0:
                row_status = "manual_review"
            else:
                row_status = "open"

        require_where = bool(constraints.get("require_where_for_mutation"))
        has_mutation = bool(re.search(r"\b(update|delete)\b", action.sql or "", flags=re.I))
        has_where = bool(re.search(r"\bwhere\b", action.sql or "", flags=re.I))
        where_status = "not_applicable"
        if require_where and has_mutation:
            where_status = "satisfied" if has_where else "missing"
        elif has_mutation:
            where_status = "open"

        policy_mappings = [
            ApprovalPolicyMapping(
                policy="allowed_operation_kinds",
                status=op_status,
                evidence=f"operation_kind={operation_kind}; allowed={sorted(allowed_kinds) if allowed_kinds else ['*']}",
            ),
            ApprovalPolicyMapping(
                policy="allowed_tables",
                status=table_status,
                evidence=(
                    f"touched={touched_tables or ['(none)']}; allowed={sorted(allowed_tables) if allowed_tables else ['*']}; "
                    f"outside={outside_tables or ['(none)']}"
                ),
            ),
            ApprovalPolicyMapping(
                policy="max_write_rows",
                status=row_status,
                evidence=f"estimated_rows={action.estimated_rows}; max_write_rows={max_write_rows}",
            ),
            ApprovalPolicyMapping(
                policy="require_where_for_mutation",
                status=where_status,
                evidence=f"require_where={require_where}; has_mutation={has_mutation}; has_where={has_where}",
            ),
        ]

        rule_reasons = self._normalize_str_list(rule.get("reasons"))
        required_actions = self._normalize_str_list(rule.get("required_actions"))
        safe_rationale = str(safe_opinion.get("rationale") or "")

        risk_points = []
        if action.requires_write:
            risk_points.append("本次请求包含写操作，存在数据变更风险。")
        if action.estimated_rows is not None:
            risk_points.append(f"预计影响行数: {action.estimated_rows}")
        if touched_tables:
            risk_points.append(f"涉及数据表: {', '.join(touched_tables)}")
        for reason in rule_reasons:
            risk_points.append(f"规则引擎: {reason}")
        if safe_rationale:
            risk_points.append(f"安全代理: {safe_rationale}")

        suggested_actions = []
        for item in required_actions:
            suggested_actions.append(f"策略要求: {item}")
        if op_status == "outside_scope":
            suggested_actions.append("操作类型不在授权范围内，请缩小权限或改为人工执行。")
        if table_status == "outside_scope":
            suggested_actions.append("触表范围超出约束，请仅保留授权表后重试。")
        if row_status in {"manual_review", "exceeds_budget"}:
            suggested_actions.append("评估影响行数并拆分批次，避免超出写入上限。")
        if where_status == "missing":
            suggested_actions.append("UPDATE/DELETE 语句需补充 WHERE 条件。")

        final_decision = str(pre_dict.get("final_decision") or "require_human")
        if final_decision in {"require_human", "block"}:
            suggested_actions.append("保持人工审批，不要自动放行。")
        if action.requires_write:
            suggested_actions.append("审批通过后先在当前分支执行，并保留可回滚版本。")

        approver_checklist = [
            "核对用户意图、SQL 摘要和本体证据是否一致。",
            "确认触表范围与预计影响行数在变更窗口内。",
            "重点检查策略映射中的 outside_scope / missing / exceeds_budget 项。",
            "写明审批理由并记录 trace_id，便于后续审计追溯。",
        ]
        if request.branch:
            approver_checklist.append(f"当前请求分支为 {request.branch}，确认是否允许在该分支执行。")

        confidence: float | None = None
        raw_confidence = safe_opinion.get("confidence")
        if isinstance(raw_confidence, (int, float)):
            confidence = max(0.0, min(1.0, float(raw_confidence)))

        return ApprovalCopilotSummary(
            recommendation=str(safe_opinion.get("recommendation") or "require_human"),
            confidence=confidence,
            final_decision=final_decision,
            risk_level=str(rule.get("risk_level") or "unknown"),
            rationale=safe_rationale,
            risk_points=self._unique_keep_order(risk_points),
            suggested_actions=self._unique_keep_order(suggested_actions),
            approver_checklist=self._unique_keep_order(approver_checklist),
            policy_mappings=policy_mappings,
        )

    def _normalize_str_list(self, value: Any) -> list[str]:
        if isinstance(value, (list, tuple, set)):
            return [str(v) for v in value if str(v).strip()]
        if value is None:
            return []
        text = str(value).strip()
        return [text] if text else []

    def _unique_keep_order(self, values: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for item in values:
            text = str(item).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            out.append(text)
        return out
