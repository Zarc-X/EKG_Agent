from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any


@dataclass(slots=True)
class SecurityBundle:
    service: Any
    Decision: Any
    OperationKind: Any
    OperationPlan: Any
    OperationContext: Any
    SecurityExecutionResult: Any


def load_security_bundle(
    *,
    audit_log_path: str,
    secret_key: str,
    safe_agent_callback: Callable[[Any, Any], dict[str, Any]] | None = None,
) -> SecurityBundle:
    """Load security_guard package from repository root.

    This keeps the refactor folder independent while reusing existing security implementation.
    """

    repo_root = Path(__file__).resolve().parents[3]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from security_guard import (  # type: ignore
        CallbackSafeAgentJudge,
        Decision,
        OperationContext,
        OperationKind,
        OperationPlan,
        SecurityExecutionResult,
        build_default_security_service,
    )

    service = build_default_security_service(
        log_file=audit_log_path,
        secret_key=secret_key,
    )

    if safe_agent_callback is not None:
        service.safe_agent = CallbackSafeAgentJudge(callback=safe_agent_callback)

    return SecurityBundle(
        service=service,
        Decision=Decision,
        OperationKind=OperationKind,
        OperationPlan=OperationPlan,
        OperationContext=OperationContext,
        SecurityExecutionResult=SecurityExecutionResult,
    )
