from __future__ import annotations

import json
from typing import Any

from app.codegen import GeneratedAction


class WarehouseAICompatAdapter:
    """Compatibility helpers for warehouse-ai tool protocol."""

    @staticmethod
    def to_duckdb_sql_tool_args(action: GeneratedAction) -> dict[str, Any]:
        purpose = "final"
        return {
            "purpose": purpose,
            "sql": action.sql,
        }

    @staticmethod
    def from_duckdb_sql_result(raw_result: str | dict[str, Any]) -> dict[str, Any]:
        if isinstance(raw_result, dict):
            return raw_result
        try:
            parsed = json.loads(raw_result)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        return {"raw": str(raw_result)}
