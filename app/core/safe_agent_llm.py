from __future__ import annotations

from typing import Any, Callable


def build_safe_agent_callback(llm_client: Any) -> Callable[[Any, Any], dict[str, Any]]:
    def callback(plan: Any, context: Any) -> dict[str, Any]:
        system_prompt = (
            "You are a strict database safety judge. "
            "Return JSON only with keys: recommendation, confidence, rationale. "
            "recommendation must be one of: allow, allow_guarded, require_human, block."
        )

        user_prompt = (
            "Evaluate operation risk.\n"
            f"user_id={getattr(context, 'user_id', '')}\n"
            f"thread_id={getattr(context, 'thread_id', '')}\n"
            f"operation_kind={getattr(getattr(plan, 'operation_kind', None), 'value', '')}\n"
            f"tool_name={getattr(plan, 'tool_name', '')}\n"
            f"touched_tables={getattr(plan, 'touched_tables', ())}\n"
            f"estimated_rows={getattr(plan, 'estimated_rows', None)}\n"
            f"requires_write={getattr(plan, 'requires_write', False)}\n"
            f"payload={getattr(plan, 'raw_payload', '')}\n"
        )

        try:
            result = llm_client.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
        except Exception as exc:
            return {
                "recommendation": "require_human",
                "confidence": 0.3,
                "rationale": f"safe-agent llm unavailable: {exc}",
            }

        recommendation = str(result.get("recommendation", "require_human")).lower().strip()
        if recommendation not in {"allow", "allow_guarded", "require_human", "block"}:
            recommendation = "require_human"

        try:
            confidence = float(result.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))

        rationale = str(result.get("rationale", "safe-agent decision"))

        return {
            "recommendation": recommendation,
            "confidence": confidence,
            "rationale": rationale,
        }

    return callback
