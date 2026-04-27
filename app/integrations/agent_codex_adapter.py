from __future__ import annotations

from app.codegen import GeneratedAction


class AgentCodexCompatAdapter:
    """Compatibility helpers for agent_codex command workflow."""

    @staticmethod
    def to_code_gen_command(user_query: str, graph_context: str) -> str:
        prompt = (
            "请基于以下电子元件本体上下文生成数据库管理代码。"
            f"\n上下文:\n{graph_context}\n需求:\n{user_query}"
        )
        return f"code_gen {prompt}"

    @staticmethod
    def to_code_accept_command(action: GeneratedAction, output_path: str = "generated/ekg_action.py") -> str:
        _ = action
        return f"code_accept {output_path}"
