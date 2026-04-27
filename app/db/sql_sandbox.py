from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(slots=True)
class SqlSandboxResult:
    allowed: bool
    reason: str
    statements: list[str]
    touched_tables: list[str]


class SqlSandboxPolicy:
    def __init__(
        self,
        *,
        max_statements: int = 8,
        allowed_verbs: set[str] | None = None,
    ) -> None:
        self.max_statements = max_statements
        self.allowed_verbs = allowed_verbs or {"SELECT", "INSERT", "UPDATE", "DELETE"}
        self._blocked_keyword_pattern = re.compile(
            r"\b(drop|alter|attach|detach|pragma|vacuum|reindex|analyze|create|truncate|replace)\b",
            flags=re.I,
        )

    def validate(self, sql: str, *, allowed_tables: set[str] | None = None) -> SqlSandboxResult:
        statements = _split_sql_statements(sql)
        if not statements:
            return SqlSandboxResult(False, "SQL is empty.", [], [])

        if len(statements) > self.max_statements:
            return SqlSandboxResult(
                False,
                f"Too many statements ({len(statements)}) exceed sandbox limit {self.max_statements}.",
                statements,
                [],
            )

        touched_tables: set[str] = set()
        for stmt in statements:
            if self._blocked_keyword_pattern.search(stmt):
                return SqlSandboxResult(False, "Blocked by sandbox keyword policy.", statements, sorted(touched_tables))

            verb = _extract_verb(stmt)
            if not verb:
                return SqlSandboxResult(False, "Cannot parse SQL verb.", statements, sorted(touched_tables))

            if verb not in self.allowed_verbs:
                return SqlSandboxResult(
                    False,
                    f"Verb '{verb}' is not allowed in sandbox.",
                    statements,
                    sorted(touched_tables),
                )

            current_tables = _extract_tables(stmt)
            touched_tables.update(current_tables)
            if allowed_tables is not None:
                unknown = [t for t in current_tables if t not in allowed_tables and not t.startswith("excel_")]
                if unknown:
                    return SqlSandboxResult(
                        False,
                        f"Statement touches unsupported tables: {', '.join(sorted(set(unknown)))}.",
                        statements,
                        sorted(touched_tables),
                    )

        return SqlSandboxResult(True, "sandbox validation passed", statements, sorted(touched_tables))


def _extract_verb(stmt: str) -> str | None:
    m = re.match(r"\s*([a-zA-Z]+)", stmt)
    if not m:
        return None
    return m.group(1).upper()


def _extract_tables(stmt: str) -> list[str]:
    patterns = [
        r"\bfrom\s+([a-zA-Z_][\w\.]*)",
        r"\bjoin\s+([a-zA-Z_][\w\.]*)",
        r"\bupdate\s+([a-zA-Z_][\w\.]*)",
        r"\binto\s+([a-zA-Z_][\w\.]*)",
        r"\bdelete\s+from\s+([a-zA-Z_][\w\.]*)",
    ]
    out: set[str] = set()
    for pattern in patterns:
        for matched in re.finditer(pattern, stmt, flags=re.I):
            out.add(matched.group(1).lower())
    return sorted(out)


def _split_sql_statements(sql: str) -> list[str]:
    parts: list[str] = []
    buffer: list[str] = []
    in_str = False
    quote = "'"

    for ch in sql:
        if ch in ("'", '"'):
            if not in_str:
                in_str = True
                quote = ch
            elif quote == ch:
                in_str = False

        if ch == ";" and not in_str:
            stmt = "".join(buffer).strip()
            if stmt:
                parts.append(stmt)
            buffer = []
            continue

        buffer.append(ch)

    tail = "".join(buffer).strip()
    if tail:
        parts.append(tail)

    return parts
