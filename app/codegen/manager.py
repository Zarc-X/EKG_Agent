from __future__ import annotations

from dataclasses import dataclass, replace
from difflib import SequenceMatcher
import re
from typing import Any


@dataclass(slots=True)
class GeneratedAction:
    operation_type: str
    sql: str
    params: tuple
    requires_write: bool
    estimated_rows: int | None
    summary: str
    python_code: str


@dataclass(slots=True)
class QueryCorrection:
    field: str
    original: str
    corrected: str
    confidence: float


class ComponentCodeGenerator:
    def __init__(
        self,
        llm_client: Any | None = None,
        part_number_vocab: list[str] | None = None,
        manufacturer_vocab: list[str] | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.part_number_vocab = sorted(
            {
                str(v).strip().upper()
                for v in (part_number_vocab or [])
                if str(v).strip()
            }
        )
        self.part_number_set = set(self.part_number_vocab)
        self.manufacturer_vocab = sorted(
            {
                str(v).strip()
                for v in (manufacturer_vocab or [])
                if str(v).strip()
            }
        )
        self.manufacturer_alias_index = self._build_manufacturer_alias_index(self.manufacturer_vocab)

    def generate(self, *, user_query: str, graph_context: str) -> GeneratedAction:
        normalized_query, corrections = self._rewrite_query_with_spelling(user_query)

        deterministic = self._generate_read_shortcuts(normalized_query)
        if deterministic is not None:
            return self._with_correction_notes(deterministic, corrections)

        if self.llm_client is not None:
            llm_action = self._generate_with_llm(user_query=normalized_query, graph_context=graph_context)
            if llm_action is not None:
                return self._with_correction_notes(llm_action, corrections)

        q = (normalized_query or "").strip()
        lower = q.lower()

        if self._is_insert(lower):
            return self._with_correction_notes(self._generate_insert(q), corrections)
        if self._is_update(lower):
            return self._with_correction_notes(self._generate_update(q), corrections)
        if self._is_delete(lower):
            return self._with_correction_notes(self._generate_delete(q), corrections)
        if self._is_bom(lower):
            return self._with_correction_notes(self._generate_bom_insert(q), corrections)
        return self._with_correction_notes(self._generate_select(q, graph_context), corrections)

    def _with_correction_notes(
        self,
        action: GeneratedAction,
        corrections: list[QueryCorrection],
    ) -> GeneratedAction:
        if not corrections:
            return action

        fragments = [
            f"{item.field}:{item.original}->{item.corrected}(置信度{item.confidence:.2f})"
            for item in corrections
        ]
        merged = "；".join(fragments)
        summary = f"{action.summary}（自动纠错：{merged}）"
        return replace(action, summary=summary)

    def _rewrite_query_with_spelling(self, user_query: str) -> tuple[str, list[QueryCorrection]]:
        query = self._normalize_query_text((user_query or "").strip())
        corrections: list[QueryCorrection] = []

        vendor_filter = self._extract_vendor_filter(query)
        if vendor_filter:
            matched_vendor, vendor_score = self._match_manufacturer(vendor_filter)
            if matched_vendor and self._normalize_vendor_key(matched_vendor) != self._normalize_vendor_key(vendor_filter):
                query = query.replace(vendor_filter, matched_vendor, 1)
                corrections.append(
                    QueryCorrection(
                        field="manufacturer",
                        original=vendor_filter,
                        corrected=matched_vendor,
                        confidence=vendor_score,
                    )
                )

        for token in self._extract_candidate_part_tokens(query):
            corrected_token, confidence = self._match_part_number(token)
            if not corrected_token:
                continue
            if corrected_token == token.upper():
                continue

            query = query.replace(token, corrected_token, 1)
            corrections.append(
                QueryCorrection(
                    field="part_number",
                    original=token,
                    corrected=corrected_token,
                    confidence=confidence,
                )
            )

        return query, corrections

    def _normalize_query_text(self, query: str) -> str:
        table = str.maketrans(
            {
                "（": "(",
                "）": ")",
                "，": ",",
                "。": ".",
                "：": ":",
                "；": ";",
                "【": "[",
                "】": "]",
                "　": " ",
            }
        )
        normalized = (query or "").translate(table)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    def _extract_candidate_part_tokens(self, query: str) -> list[str]:
        tokens: list[str] = []
        seen: set[str] = set()
        for match in re.finditer(r"[A-Za-z][A-Za-z0-9\-]{5,}", query):
            token = match.group(0)
            upper_token = token.upper()
            if upper_token in seen:
                continue
            if re.fullmatch(r"C\d{5,}", upper_token):
                continue
            if not re.search(r"\d", upper_token):
                continue
            seen.add(upper_token)
            tokens.append(token)
        return tokens

    def _match_part_number(self, raw_token: str) -> tuple[str | None, float]:
        token = (raw_token or "").strip().upper()
        if not token:
            return None, 0.0
        if token in self.part_number_set:
            return token, 1.0
        if not self.part_number_vocab:
            return None, 0.0

        best_candidate = ""
        best_score = 0.0
        for candidate in self.part_number_vocab:
            score = SequenceMatcher(None, token, candidate).ratio()
            if score > best_score:
                best_score = score
                best_candidate = candidate

        if not best_candidate:
            return None, best_score

        distance = self._levenshtein_distance(token, best_candidate)
        max_distance = 1 if len(token) < 12 else 2
        if best_score >= 0.84 and distance <= max_distance:
            return best_candidate, best_score
        return None, best_score

    def _build_manufacturer_alias_index(self, manufacturers: list[str]) -> list[tuple[str, str]]:
        index: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for manufacturer in manufacturers:
            aliases = {self._normalize_vendor_key(manufacturer)}

            for piece in re.findall(r"[A-Za-z0-9\-_]+", manufacturer):
                aliases.add(self._normalize_vendor_key(piece))
            for piece in re.findall(r"[\u4e00-\u9fff]+", manufacturer):
                aliases.add(self._normalize_vendor_key(piece))

            for alias in aliases:
                if not alias:
                    continue
                pair = (alias, manufacturer)
                if pair in seen:
                    continue
                seen.add(pair)
                index.append(pair)
        return index

    def _match_manufacturer(self, raw_vendor: str) -> tuple[str | None, float]:
        vendor_key = self._normalize_vendor_key(raw_vendor)
        if not vendor_key:
            return None, 0.0

        if not self.manufacturer_vocab:
            return None, 0.0

        for vendor in self.manufacturer_vocab:
            if self._normalize_vendor_key(vendor) == vendor_key:
                return vendor, 1.0

        best_vendor = ""
        best_score = 0.0
        for alias, vendor in self.manufacturer_alias_index:
            score = SequenceMatcher(None, vendor_key, alias).ratio()
            if (vendor_key in alias or alias in vendor_key) and min(len(vendor_key), len(alias)) >= 4:
                score = max(score, 0.92)
            if score > best_score:
                best_score = score
                best_vendor = vendor

        if best_vendor and best_score >= 0.86:
            return best_vendor, best_score
        return None, best_score

    def _levenshtein_distance(self, left: str, right: str) -> int:
        if left == right:
            return 0
        if not left:
            return len(right)
        if not right:
            return len(left)

        prev = list(range(len(right) + 1))
        for i, left_char in enumerate(left, start=1):
            current = [i]
            for j, right_char in enumerate(right, start=1):
                insertion = current[j - 1] + 1
                deletion = prev[j] + 1
                replace_cost = prev[j - 1] + (0 if left_char == right_char else 1)
                current.append(min(insertion, deletion, replace_cost))
            prev = current
        return prev[-1]

    def _generate_with_llm(self, *, user_query: str, graph_context: str) -> GeneratedAction | None:
        schema_hint = (
            "Schema:\n"
            "components(part_number, name, category, package, voltage, current, manufacturer, purchase_date, purchase_id, description, created_at, updated_at)\n"
            "inventory(part_number, quantity, location, updated_at)\n"
            "bom(parent_part_number, child_part_number, qty)\n"
            "Notes: inventory has quantity, not stock. Use components.manufacturer for vendor/brand and components.purchase_date for buy date."
        )

        system_prompt = (
            "You are a senior code agent for electronic-component database operations. "
            "Return JSON only with keys: operation_type, sql, params, requires_write, "
            "estimated_rows, summary, python_code. "
            "operation_type must be read or write. "
            "Use SQLite-compatible SQL. Prefer parameterized SQL using ? placeholders. "
            "Only use tables/columns that exist in the provided schema."
        )
        user_prompt = (
            "User request:\n"
            f"{user_query}\n\n"
            f"{schema_hint}\n\n"
            "Graph context:\n"
            f"{graph_context}\n\n"
            "Please generate one executable action as JSON."
        )

        try:
            payload = self.llm_client.generate_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        except Exception:
            return None

        if not isinstance(payload, dict):
            return None

        sql = str(payload.get("sql", "")).strip()
        if not sql:
            return None

        operation_type = str(payload.get("operation_type", "")).strip().lower()
        if operation_type not in {"read", "write"}:
            operation_type = self._infer_operation_type_from_sql(sql)

        params = self._normalize_params(payload.get("params", []))
        requires_write = bool(payload.get("requires_write", operation_type == "write"))

        estimated_rows = self._to_optional_int(payload.get("estimated_rows"))
        summary = str(payload.get("summary", "")).strip() or f"LLM generated {operation_type} action"
        python_code = str(payload.get("python_code", "")).strip() or self._build_python_from_sql(sql)

        return GeneratedAction(
            operation_type=operation_type,
            sql=sql,
            params=params,
            requires_write=requires_write,
            estimated_rows=estimated_rows,
            summary=summary,
            python_code=python_code,
        )

    def _infer_operation_type_from_sql(self, sql: str) -> str:
        head = sql.strip().split(" ", 1)[0].lower() if sql.strip() else ""
        if head in {"insert", "update", "delete", "replace", "merge", "alter", "drop", "create"}:
            return "write"
        return "read"

    def _generate_read_shortcuts(self, user_query: str) -> GeneratedAction | None:
        query = (user_query or "").strip()
        part_number = self._extract_part_number(query)
        purchase_id = self._extract_purchase_id(query)

        if part_number and ("库存" in query or "在库" in query):
            sql = "SELECT SUM(i.quantity) AS total_quantity FROM inventory i WHERE i.part_number = ?"
            return GeneratedAction(
                operation_type="read",
                sql=sql,
                params=(part_number,),
                requires_write=False,
                estimated_rows=1,
                summary=f"查询型号 {part_number} 的库存",
                python_code=self._build_python_from_sql(sql),
            )

        if part_number and any(k in query for k in ["厂商", "品牌", "manufacturer"]):
            sql = "SELECT c.part_number, c.manufacturer FROM components c WHERE c.part_number = ?"
            return GeneratedAction(
                operation_type="read",
                sql=sql,
                params=(part_number,),
                requires_write=False,
                estimated_rows=1,
                summary=f"查询型号 {part_number} 的厂商",
                python_code=self._build_python_from_sql(sql),
            )

        if part_number and any(k in query for k in ["购买日期", "采购日期"]):
            sql = "SELECT c.part_number, c.purchase_date FROM components c WHERE c.part_number = ?"
            return GeneratedAction(
                operation_type="read",
                sql=sql,
                params=(part_number,),
                requires_write=False,
                estimated_rows=1,
                summary=f"查询型号 {part_number} 的购买日期",
                python_code=self._build_python_from_sql(sql),
            )

        vendor_filter = self._extract_vendor_filter(query)
        if vendor_filter:
            vendor_like = f"%{self._normalize_vendor_text(vendor_filter)}%"
            sql = (
                "SELECT c.part_number, c.name, c.manufacturer, c.category, c.package "
                "FROM components c "
                "WHERE lower(replace(replace(c.manufacturer, '（', '('), '）', ')')) LIKE lower(?) "
                "ORDER BY c.part_number LIMIT 200"
            )
            return GeneratedAction(
                operation_type="read",
                sql=sql,
                params=(vendor_like,),
                requires_write=False,
                estimated_rows=50,
                summary=f"查询厂商 {vendor_filter} 的元件列表",
                python_code=self._build_python_from_sql(sql),
            )

        if purchase_id and any(k in query for k in ["库存", "在库", "物料编码"]):
            sql = (
                "SELECT c.purchase_id, c.part_number, i.quantity "
                "FROM components c LEFT JOIN inventory i ON c.part_number = i.part_number "
                "WHERE c.purchase_id = ?"
            )
            return GeneratedAction(
                operation_type="read",
                sql=sql,
                params=(purchase_id,),
                requires_write=False,
                estimated_rows=10,
                summary=f"查询采购单号 {purchase_id} 对应物料与库存",
                python_code=self._build_python_from_sql(sql),
            )

        if purchase_id and any(k in query for k in ["购买日期", "采购日期"]):
            sql = "SELECT c.purchase_id, c.part_number, c.purchase_date FROM components c WHERE c.purchase_id = ?"
            return GeneratedAction(
                operation_type="read",
                sql=sql,
                params=(purchase_id,),
                requires_write=False,
                estimated_rows=10,
                summary=f"查询采购单号 {purchase_id} 的购买日期",
                python_code=self._build_python_from_sql(sql),
            )

        return None

    def _normalize_params(self, params: Any) -> tuple:
        if isinstance(params, (list, tuple)):
            return tuple(params)
        if params in (None, ""):
            return tuple()
        return (params,)

    def _to_optional_int(self, value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _build_python_from_sql(self, sql: str) -> str:
        escaped = sql.replace("'''", "\"\"\"")
        return (
            "def run_action(conn, params=()):\n"
            f"    sql = '''{escaped}'''\n"
            "    return conn.execute(sql, tuple(params))\n"
        )

    def _is_insert(self, q: str) -> bool:
        return any(k in q for k in ["新增", "添加", "插入", "create component", "add component"])

    def _is_update(self, q: str) -> bool:
        return any(k in q for k in ["更新", "修改", "update", "set"])

    def _is_delete(self, q: str) -> bool:
        return any(k in q for k in ["删除", "移除", "delete", "remove"])

    def _is_bom(self, q: str) -> bool:
        return "bom" in q or "物料清单" in q

    def _extract_part_number(self, text: str) -> str | None:
        patterns = [
            r"型号[:：\s]*([A-Za-z0-9\-]+)",
            r"part[_\s-]?number[:：\s]*([A-Za-z0-9\-]+)",
            r"(?<![A-Za-z0-9\-])([A-Z]{2,}\d[A-Za-z0-9\-]*)(?![A-Za-z0-9\-])",
        ]
        for p in patterns:
            m = re.search(p, text, flags=re.I)
            if m:
                return m.group(1).upper()

        for m in re.finditer(r"[A-Za-z]{2,}\d[A-Za-z0-9\-]{4,}", text, flags=re.I):
            token = m.group(0).upper()
            if re.fullmatch(r"C\d{5,}", token):
                continue
            return token
        return None

    def _extract_purchase_id(self, text: str) -> str | None:
        patterns = [
            r"采购单号[:：\s]*([A-Za-z0-9\-]+)",
            r"\b(C\d{5,})\b",
        ]
        for p in patterns:
            m = re.search(p, text, flags=re.I)
            if m:
                return m.group(1).upper()
        return None

    def _extract_vendor_filter(self, text: str) -> str | None:
        patterns = [
            r"(?:厂商|品牌)\s*(?:为|是|:|：)?\s*(.+?)(?:的|$)",
            r"(?:厂商|品牌)\s*(?:为|是|:|：)?\s*([^\s,，。；;]+)",
        ]
        for p in patterns:
            m = re.search(p, text)
            if m:
                value = (m.group(1) or "").strip().strip("'\"“”‘’")
                if value:
                    return value
        return None

    def _normalize_vendor_text(self, value: str) -> str:
        out = (value or "").strip()
        out = out.strip("'\"“”‘’")
        out = re.sub(r"\s+", "", out)
        out = re.sub(r"(?:的所有电子元件|的所有元件|的器件列表|的元件列表)$", "", out)
        out = out.strip()
        return out

    def _normalize_vendor_key(self, value: str) -> str:
        out = self._normalize_vendor_text(value)
        out = out.replace("（", "(").replace("）", ")")
        out = out.replace("(", "").replace(")", "")
        out = out.lower()
        out = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", out)
        return out

    def _extract_name(self, text: str) -> str:
        m = re.search(r"名称[:：\s]*([\w\-\u4e00-\u9fff]+)", text)
        if m:
            return m.group(1)
        return "AutoGeneratedComponent"

    def _extract_category(self, text: str) -> str:
        m = re.search(r"分类[:：\s]*([\w\-\u4e00-\u9fff]+)", text)
        if m:
            return m.group(1)
        return "Unknown"

    def _generate_select(self, user_query: str, graph_context: str) -> GeneratedAction:
        part = self._extract_part_number(user_query)
        if part:
            sql = (
                "SELECT c.part_number, c.name, c.manufacturer, c.purchase_date, c.category, c.package, i.quantity, i.location "
                "FROM components c LEFT JOIN inventory i ON c.part_number=i.part_number "
                "WHERE c.part_number = ?"
            )
            params = (part,)
            summary = f"查询型号 {part} 的电子元件数据"
            py = (
                "def query_component(conn, part_number):\n"
                "    sql = '''SELECT c.part_number, c.name, c.manufacturer, c.purchase_date, c.category, c.package, i.quantity, i.location "
                "FROM components c LEFT JOIN inventory i ON c.part_number=i.part_number "
                "WHERE c.part_number = ?'''\n"
                "    return conn.execute(sql, (part_number,)).fetchall()\n"
            )
            return GeneratedAction("read", sql, params, False, 1, summary, py)

        sql = "SELECT part_number, name, category, package FROM components ORDER BY part_number LIMIT ?"
        py = (
            "def list_components(conn, limit=50):\n"
            "    sql = 'SELECT part_number, name, category, package FROM components ORDER BY part_number LIMIT ?'\n"
            "    return conn.execute(sql, (limit,)).fetchall()\n"
        )
        summary = "列出电子元件列表"
        return GeneratedAction("read", sql, (50,), False, 50, summary, py)

    def _generate_insert(self, user_query: str) -> GeneratedAction:
        part = self._extract_part_number(user_query) or "AUTO_PART_001"
        name = self._extract_name(user_query)
        category = self._extract_category(user_query)

        sql = (
            "INSERT INTO components "
            "(part_number, name, category, package, voltage, current, manufacturer, purchase_date, purchase_id, description, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))"
        )
        params = (part, name, category, "UNKNOWN", "", "", "", "", "", "generated by agent")
        py = (
            "def add_component(conn, part_number, name, category):\n"
            "    sql = '''INSERT INTO components "
            "(part_number, name, category, package, voltage, current, manufacturer, purchase_date, purchase_id, description, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))'''\n"
            "    return conn.execute(sql, (part_number, name, category, 'UNKNOWN', '', '', '', '', '', 'generated by agent'))\n"
        )
        return GeneratedAction("write", sql, params, True, 1, f"新增元件 {part}", py)

    def _generate_update(self, user_query: str) -> GeneratedAction:
        part = self._extract_part_number(user_query) or "STM32F103C8T6"
        m = re.search(r"库存[:：\s]*(\d+)", user_query)
        quantity = int(m.group(1)) if m else 100

        sql = "UPDATE inventory SET quantity = ?, updated_at = datetime('now') WHERE part_number = ?"
        params = (quantity, part)
        py = (
            "def update_inventory(conn, part_number, quantity):\n"
            "    sql = 'UPDATE inventory SET quantity = ?, updated_at = datetime(\'now\') WHERE part_number = ?'\n"
            "    return conn.execute(sql, (quantity, part_number))\n"
        )
        return GeneratedAction("write", sql, params, True, 1, f"更新 {part} 库存为 {quantity}", py)

    def _generate_delete(self, user_query: str) -> GeneratedAction:
        part = self._extract_part_number(user_query) or "STM32F103C8T6"
        sql = "DELETE FROM components WHERE part_number = ?"
        params = (part,)
        py = (
            "def delete_component(conn, part_number):\n"
            "    sql = 'DELETE FROM components WHERE part_number = ?'\n"
            "    return conn.execute(sql, (part_number,))\n"
        )
        return GeneratedAction("write", sql, params, True, 1, f"删除元件 {part}", py)

    def _generate_bom_insert(self, user_query: str) -> GeneratedAction:
        parts = re.findall(r"[A-Z]{2,}\d[A-Za-z0-9\-]*", user_query)
        parent = parts[0] if len(parts) > 0 else "STM32F103C8T6"
        child = parts[1] if len(parts) > 1 else "TPS5430"

        m = re.search(r"数量[:：\s]*(\d+(?:\.\d+)?)", user_query)
        qty = float(m.group(1)) if m else 1.0

        sql = "INSERT OR REPLACE INTO bom (parent_part_number, child_part_number, qty) VALUES (?, ?, ?)"
        params = (parent, child, qty)
        py = (
            "def upsert_bom(conn, parent_part_number, child_part_number, qty):\n"
            "    sql = 'INSERT OR REPLACE INTO bom (parent_part_number, child_part_number, qty) VALUES (?, ?, ?)'\n"
            "    return conn.execute(sql, (parent_part_number, child_part_number, qty))\n"
        )
        return GeneratedAction("write", sql, params, True, 1, f"维护 BOM: {parent} -> {child}", py)
