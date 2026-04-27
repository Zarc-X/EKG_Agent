from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock
from typing import Any
import uuid

from .models import ApprovalTicket


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ApprovalService:
    def __init__(self) -> None:
        self._lock = RLock()
        self._tickets: dict[str, ApprovalTicket] = {}
        self._ticket_payloads: dict[str, dict[str, Any]] = {}

    def create_ticket(
        self,
        *,
        trace_id: str,
        requester: str,
        summary: str,
        payload: dict[str, Any],
    ) -> ApprovalTicket:
        with self._lock:
            ticket_id = str(uuid.uuid4())
            now = _now()
            ticket = ApprovalTicket(
                ticket_id=ticket_id,
                trace_id=trace_id,
                status="pending",
                summary=summary,
                created_at=now,
                updated_at=now,
                requester=requester,
            )
            self._tickets[ticket_id] = ticket
            self._ticket_payloads[ticket_id] = payload
            return ticket

    def list_tickets(self, status: str | None = None) -> list[ApprovalTicket]:
        with self._lock:
            values = list(self._tickets.values())
            if status:
                values = [v for v in values if v.status == status]
            return sorted(values, key=lambda x: x.created_at, reverse=True)

    def get_ticket(self, ticket_id: str) -> ApprovalTicket | None:
        with self._lock:
            return self._tickets.get(ticket_id)

    def get_payload(self, ticket_id: str) -> dict[str, Any] | None:
        with self._lock:
            payload = self._ticket_payloads.get(ticket_id)
            return dict(payload) if payload else None

    def decide(self, *, ticket_id: str, approved: bool, approver: str, reason: str | None) -> ApprovalTicket:
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if ticket is None:
                raise ValueError(f"ticket not found: {ticket_id}")
            if ticket.status not in {"pending"}:
                raise ValueError(f"ticket is not pending: {ticket.status}")

            ticket.status = "approved" if approved else "rejected"
            ticket.approver = approver
            ticket.reason = reason
            ticket.updated_at = _now()
            self._tickets[ticket_id] = ticket
            return ticket

    def mark_executed(self, ticket_id: str) -> ApprovalTicket:
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if ticket is None:
                raise ValueError(f"ticket not found: {ticket_id}")
            ticket.status = "executed"
            ticket.updated_at = _now()
            self._tickets[ticket_id] = ticket
            return ticket

    def mark_failed(self, ticket_id: str, reason: str) -> ApprovalTicket:
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if ticket is None:
                raise ValueError(f"ticket not found: {ticket_id}")
            ticket.status = "failed"
            ticket.reason = reason
            ticket.updated_at = _now()
            self._tickets[ticket_id] = ticket
            return ticket
