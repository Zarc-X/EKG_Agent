from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

from openai import OpenAI


@dataclass(slots=True)
class OpenAICompatLLMClientConfig:
    api_key: str
    base_url: str
    model: str
    timeout_s: float = 60.0
    temperature: float = 0.1


class OpenAICompatLLMClient:
    def __init__(self, config: OpenAICompatLLMClientConfig) -> None:
        self.config = config
        self.client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.timeout_s,
        )

    def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                temperature=self.config.temperature,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except Exception:
            response = self.client.chat.completions.create(
                model=self.config.model,
                temperature=self.config.temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )

        content = response.choices[0].message.content or "{}"
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    maybe = item.get("text")
                    if isinstance(maybe, str):
                        parts.append(maybe)
            content = "\n".join(parts) if parts else "{}"

        if not isinstance(content, str):
            content = str(content)

        return self._extract_json(content)

    def _extract_json(self, text: str) -> dict[str, Any]:
        text = text.strip()

        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

        fence_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, flags=re.I)
        if fence_match:
            candidate = fence_match.group(1)
            try:
                data = json.loads(candidate)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass

        raw_match = re.search(r"(\{[\s\S]*\})", text)
        if raw_match:
            candidate = raw_match.group(1)
            try:
                data = json.loads(candidate)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass

        best_effort = self._extract_known_fields(text)
        if best_effort:
            return best_effort

        return {"raw": text}

    def _extract_known_fields(self, text: str) -> dict[str, Any]:
        out: dict[str, Any] = {}

        def extract_string(key: str) -> str | None:
            m = re.search(rf'"{key}"\s*:\s*"((?:\\.|[^"\\])*)"', text)
            if not m:
                return None
            return bytes(m.group(1), "utf-8").decode("unicode_escape")

        def extract_bool(key: str) -> bool | None:
            m = re.search(rf'"{key}"\s*:\s*(true|false)', text, flags=re.I)
            if not m:
                return None
            return m.group(1).lower() == "true"

        def extract_int(key: str) -> int | None:
            m = re.search(rf'"{key}"\s*:\s*(-?\d+)', text)
            if not m:
                return None
            try:
                return int(m.group(1))
            except ValueError:
                return None

        op = extract_string("operation_type")
        sql = extract_string("sql")
        summary = extract_string("summary")

        if op is not None:
            out["operation_type"] = op
        if sql is not None:
            out["sql"] = sql
        if summary is not None:
            out["summary"] = summary

        req_write = extract_bool("requires_write")
        if req_write is not None:
            out["requires_write"] = req_write

        est_rows = extract_int("estimated_rows")
        if est_rows is not None:
            out["estimated_rows"] = est_rows

        params_match = re.search(r'"params"\s*:\s*(\[[\s\S]*?\])', text)
        if params_match:
            try:
                parsed = json.loads(params_match.group(1))
                if isinstance(parsed, list):
                    out["params"] = parsed
            except json.JSONDecodeError:
                pass

        py_code_match = re.search(r'"python_code"\s*:\s*"""([\s\S]*?)"""', text)
        if py_code_match:
            out["python_code"] = py_code_match.group(1).strip("\n")
        else:
            py_code = extract_string("python_code")
            if py_code is not None:
                out["python_code"] = py_code

        return out
