from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from typing import Any

from .entity_linker import EntityLinker, tokenize
from .ontology_store import OntologyStore


@dataclass(slots=True)
class GraphEvidence:
    node_id: str
    title: str
    score: float
    relation_summary: str


@dataclass(slots=True)
class GraphRAGResult:
    context: str
    evidence: list[GraphEvidence]


class GraphRAGService:
    _CONTROL_HINTS: dict[str, list[str]] = {
        "update": ["update", "write_query", "mutation", "touches_table"],
        "insert": ["insert", "write_query", "mutation", "touches_table"],
        "delete": ["delete", "write_query", "mutation", "touches_table"],
        "rollback": ["rollback", "version", "derived_from", "rollback_target"],
        "approve": ["approval", "change_event", "on_branch"],
        "inventory": ["inventory", "table", "touches_table"],
        "库存": ["inventory", "table", "touches_table"],
        "写": ["write_query", "mutation", "touches_table"],
        "回滚": ["rollback", "version", "rollback_target"],
        "审批": ["approval", "change_event", "on_branch"],
    }

    def __init__(
        self,
        store: OntologyStore,
        linker: EntityLinker,
        *,
        iterations: int = 2,
        iteration_top_k: int = 8,
        max_query_terms: int = 24,
        semantic_weight: float = 0.65,
        control_weight: float = 0.35,
        adaptive_stop_enabled: bool = True,
        adaptive_min_gain: float = 0.08,
        adaptive_min_new_nodes: int = 1,
        adaptive_stable_rounds: int = 1,
    ) -> None:
        self.store = store
        self.linker = linker
        self.iterations = max(1, int(iterations))
        self.iteration_top_k = max(3, int(iteration_top_k))
        self.max_query_terms = max(8, int(max_query_terms))
        self.semantic_weight = min(max(float(semantic_weight), 0.0), 1.0)
        self.control_weight = min(max(float(control_weight), 0.0), 1.0)
        if self.semantic_weight + self.control_weight <= 0:
            self.semantic_weight = 0.65
            self.control_weight = 0.35
        else:
            total = self.semantic_weight + self.control_weight
            self.semantic_weight /= total
            self.control_weight /= total
        self.adaptive_stop_enabled = bool(adaptive_stop_enabled)
        self.adaptive_min_gain = max(0.0, float(adaptive_min_gain))
        self.adaptive_min_new_nodes = max(0, int(adaptive_min_new_nodes))
        self.adaptive_stable_rounds = max(1, int(adaptive_stable_rounds))

        self._semantic_index: dict[str, set[str]] = {}
        self._control_index: dict[str, set[str]] = {}
        self._degree_index: dict[str, int] = {}
        self._rebuild_dual_layer_index()

    def retrieve(self, query: str, top_k: int = 5, hops: int = 1) -> GraphRAGResult:
        target_k = max(1, int(top_k))
        target_hops = max(1, int(hops))

        base_tokens = tokenize(query)
        if not base_tokens:
            return GraphRAGResult(
                context="- no graph match, query tokens: (empty)",
                evidence=[],
            )

        query_terms = self._expand_query_terms_with_control_hints(base_tokens)
        node_scores: dict[str, float] = defaultdict(float)
        relation_terms: set[str] = set()
        rounds_completed = 0
        stagnation_rounds = 0
        stop_reason = "max_iterations"
        round_stats: list[str] = []

        for round_idx in range(self.iterations):
            rounds_completed += 1
            before_scores = dict(node_scores)
            before_nodes = set(before_scores.keys())
            before_terms = list(query_terms)

            query_text = " ".join(query_terms[: self.max_query_terms])
            semantic_candidates = self.linker.link(query_text, top_k=max(target_k, self.iteration_top_k))
            control_candidates = self._search_dual_layer(query_terms, top_k=max(target_k, self.iteration_top_k))
            merged = self._merge_candidates(
                semantic_candidates=semantic_candidates,
                control_candidates=control_candidates,
                limit=max(target_k, self.iteration_top_k),
            )
            if not merged:
                stop_reason = "no_candidates"
                break

            max_rank = max(1, len(merged) - 1)
            current_round_nodes: list[str] = []
            avg_semantic = 0.0
            avg_control = 0.0
            for rank, (node_id, fused_score, semantic_score, control_score) in enumerate(merged):
                node = self.store.nodes.get(node_id)
                if node is None:
                    continue

                current_round_nodes.append(node_id)

                round_weight = 1.0 / (round_idx + 1)
                rank_weight = 1.0 + (max_rank - rank) / max_rank
                node_scores[node_id] += fused_score * round_weight * rank_weight
                avg_semantic += semantic_score
                avg_control += control_score
                relation_terms.update(self._collect_relation_terms(node_id=node_id, hops=1, limit=8))

            if current_round_nodes:
                size = len(current_round_nodes)
                avg_semantic /= size
                avg_control /= size

            query_terms = self._build_next_query_terms(
                base_tokens=base_tokens,
                node_scores=node_scores,
                relation_terms=relation_terms,
            )
            query_terms = self._expand_query_terms_with_control_hints(query_terms)

            new_nodes = len(set(current_round_nodes) - before_nodes)
            gain = self._compute_gain(
                previous_scores=before_scores,
                current_scores=node_scores,
                focus_nodes=current_round_nodes,
            )
            terms_changed = query_terms != before_terms
            round_stats.append(
                (
                    f"r{round_idx + 1}:gain={gain:.4f},new_nodes={new_nodes},"
                    f"terms_changed={terms_changed},avg_sem={avg_semantic:.3f},avg_ctrl={avg_control:.3f}"
                )
            )

            if self.adaptive_stop_enabled and (round_idx + 1) < self.iterations:
                low_gain = gain < self.adaptive_min_gain
                low_new_nodes = new_nodes < self.adaptive_min_new_nodes
                if low_gain and (low_new_nodes or not terms_changed):
                    stagnation_rounds += 1
                else:
                    stagnation_rounds = 0

                if stagnation_rounds >= self.adaptive_stable_rounds:
                    stop_reason = (
                        "adaptive_stop:low_gain"
                        f"(gain={gain:.4f},new_nodes={new_nodes},terms_changed={terms_changed})"
                    )
                    break

        if not node_scores:
            fallback = ", ".join(base_tokens[:8])
            return GraphRAGResult(
                context=f"- no graph match, query tokens: {fallback}",
                evidence=[],
            )

        expanded_scores = dict(node_scores)
        for node_id, seed_score in sorted(node_scores.items(), key=lambda item: item[1], reverse=True)[: max(target_k, self.iteration_top_k)]:
            for candidate_id, depth in self._bfs_distances(seed_id=node_id, depth=target_hops).items():
                if candidate_id == node_id:
                    continue
                expanded_scores[candidate_id] = expanded_scores.get(candidate_id, 0.0) + (seed_score * 0.35 / (depth + 1))

        ranked = sorted(expanded_scores.items(), key=lambda item: item[1], reverse=True)
        evidence: list[GraphEvidence] = []
        context_lines: list[str] = [
            "- retrieval_mode: ras_iterative_dual_layer",
            "  - index_layers: semantic+control",
            f"  - layer_weights: semantic={self.semantic_weight:.2f}, control={self.control_weight:.2f}",
            f"  - rounds: {rounds_completed}",
            f"  - stop_reason: {stop_reason}",
            f"  - adaptive_stop: {self.adaptive_stop_enabled}",
            f"  - initial_terms: {', '.join(base_tokens[:8])}",
            f"  - refined_terms: {', '.join(query_terms[:8])}",
            f"  - round_stats: {' | '.join(round_stats[:4]) if round_stats else 'n/a'}",
        ]

        for node_id, score in ranked[:target_k]:
            node = self.store.nodes.get(node_id)
            if node is None:
                continue

            relations = self._collect_relation_lines(node_id=node_id, hops=target_hops)
            relation_summary = " | ".join(relations[:3]) if relations else "no direct relation"

            evidence.append(
                GraphEvidence(
                    node_id=node.node_id,
                    title=node.name,
                    score=round(score, 4),
                    relation_summary=relation_summary,
                )
            )
            context_lines.append(f"- {self.store.as_context_line(node.node_id)}")
            for rel in relations[:3]:
                context_lines.append(f"  - relation: {rel}")

        if len(context_lines) <= 4:
            fallback = ", ".join(base_tokens[:8])
            context_lines.append(f"- no graph match, query tokens: {fallback}")

        return GraphRAGResult(context="\n".join(context_lines), evidence=evidence)

    def _build_next_query_terms(
        self,
        *,
        base_tokens: list[str],
        node_scores: dict[str, float],
        relation_terms: set[str],
    ) -> list[str]:
        terms: list[str] = list(base_tokens)
        top_nodes = sorted(node_scores.items(), key=lambda item: item[1], reverse=True)[:6]

        for node_id, _score in top_nodes:
            node = self.store.nodes.get(node_id)
            if node is None:
                continue
            terms.extend(tokenize(node.name))
            for alias in node.aliases[:4]:
                terms.extend(tokenize(alias))
            for key, value in list(node.attributes.items())[:4]:
                terms.extend(tokenize(str(key)))
                terms.extend(tokenize(str(value)))

        terms.extend(sorted(relation_terms))

        refined: list[str] = []
        seen: set[str] = set()
        for term in terms:
            text = str(term).strip().lower()
            if not text or text in seen:
                continue
            if len(text) <= 1:
                continue
            seen.add(text)
            refined.append(text)
            if len(refined) >= self.max_query_terms:
                break

        return refined if refined else base_tokens

    def refresh_index(self) -> dict[str, int]:
        self._rebuild_dual_layer_index()
        return {
            "nodes": len(self._semantic_index),
            "control_nodes": len(self._control_index),
            "edges": len(self.store.edges),
        }

    def apply_ontology_incremental_update(
        self,
        *,
        thread_id: str,
        branch: str,
        user_id: str | None,
        trace_id: str | None,
        change_log: dict[str, Any],
        version_id: str | None,
        parent_version_id: str | None,
        recorded_at: str | None = None,
    ) -> dict[str, Any]:
        operation_type = str(change_log.get("operation_type", "write")).strip().lower() or "write"
        summary = str(change_log.get("summary", "change event")).strip() or "change event"
        touched_tables = [str(item).strip() for item in change_log.get("touched_tables", []) if str(item).strip()]
        rowcount = int(change_log.get("rowcount", 0) or 0)
        sql_text = str(change_log.get("sql", "")).strip()
        timestamp = recorded_at or datetime.now(timezone.utc).isoformat()

        event_id = self._make_event_id(trace_id=trace_id, summary=summary, timestamp=timestamp)
        event_aliases = [operation_type, "change_event", branch]
        event_aliases.extend(tokenize(summary)[:8])
        self._upsert_node_merge(
            node_id=event_id,
            name=f"变更事件: {summary[:48]}",
            node_type="ChangeEvent",
            aliases=event_aliases,
            attributes={
                "operation_type": operation_type,
                "summary": summary,
                "thread_id": thread_id,
                "branch": branch,
                "trace_id": trace_id,
                "rowcount": rowcount,
                "touched_tables": touched_tables,
                "sql_preview": sql_text[:300],
                "recorded_at": timestamp,
            },
        )

        branch_node_id = f"branch:{thread_id}:{branch}".lower()
        self._upsert_node_merge(
            node_id=branch_node_id,
            name=f"分支 {branch}",
            node_type="BranchContext",
            aliases=[branch, thread_id],
            attributes={"thread_id": thread_id, "branch": branch, "updated_at": timestamp},
        )
        self.store.add_edge(source=event_id, target=branch_node_id, relation="on_branch", attributes={"at": timestamp})

        if user_id:
            user_node_id = f"user:{user_id}".lower()
            self._upsert_node_merge(
                node_id=user_node_id,
                name=f"用户 {user_id}",
                node_type="Actor",
                aliases=[user_id],
                attributes={"user_id": user_id, "updated_at": timestamp},
            )
            self.store.add_edge(
                source=user_node_id,
                target=event_id,
                relation="initiates_change",
                attributes={"at": timestamp},
            )

        for table in touched_tables:
            table_node_id = f"table:{table}".lower()
            self._upsert_node_merge(
                node_id=table_node_id,
                name=f"表 {table}",
                node_type="DataTable",
                aliases=[table],
                attributes={
                    "table": table,
                    "last_operation": operation_type,
                    "last_rowcount": rowcount,
                    "updated_at": timestamp,
                },
            )
            self.store.add_edge(
                source=event_id,
                target=table_node_id,
                relation="touches_table",
                attributes={"operation_type": operation_type, "rowcount": rowcount, "at": timestamp},
            )

        version_node_id: str | None = None
        if version_id:
            version_node_id = f"version:{version_id}".lower()
            self._upsert_node_merge(
                node_id=version_node_id,
                name=f"版本 {version_id[:8]}",
                node_type="VersionSnapshot",
                aliases=[version_id],
                attributes={"version_id": version_id, "branch": branch, "updated_at": timestamp},
            )
            self.store.add_edge(
                source=event_id,
                target=version_node_id,
                relation="produced_version",
                attributes={"at": timestamp},
            )

        if parent_version_id:
            parent_node_id = f"version:{parent_version_id}".lower()
            self._upsert_node_merge(
                node_id=parent_node_id,
                name=f"版本 {parent_version_id[:8]}",
                node_type="VersionSnapshot",
                aliases=[parent_version_id],
                attributes={"version_id": parent_version_id, "updated_at": timestamp},
            )
            self.store.add_edge(
                source=event_id,
                target=parent_node_id,
                relation="derived_from",
                attributes={"at": timestamp},
            )
            if version_node_id:
                self.store.add_edge(
                    source=version_node_id,
                    target=parent_node_id,
                    relation="derived_from",
                    attributes={"at": timestamp},
                )

        self.store.save()
        index_stats = self.refresh_index()
        return {
            "status": "updated",
            "event_id": event_id,
            "tables": touched_tables,
            "index": index_stats,
        }

    def _expand_query_terms_with_control_hints(self, terms: list[str]) -> list[str]:
        expanded = list(terms)
        low_terms = [str(term).strip().lower() for term in terms if str(term).strip()]
        for term in low_terms:
            hints = self._CONTROL_HINTS.get(term)
            if not hints:
                continue
            expanded.extend(hints)

        refined: list[str] = []
        seen: set[str] = set()
        for term in expanded:
            token = str(term).strip().lower()
            if not token or token in seen:
                continue
            seen.add(token)
            refined.append(token)
            if len(refined) >= self.max_query_terms:
                break
        return refined

    def _search_dual_layer(self, query_terms: list[str], top_k: int) -> list[tuple[str, float, float, float]]:
        if not query_terms:
            return []

        terms = {term for term in query_terms if term}
        if not terms:
            return []

        scores: list[tuple[str, float, float, float]] = []
        candidate_ids = set(self._semantic_index.keys()) | set(self._control_index.keys())
        for node_id in candidate_ids:
            semantic_tokens = self._semantic_index.get(node_id, set())
            control_tokens = self._control_index.get(node_id, set())
            semantic_overlap = len(terms & semantic_tokens)
            control_overlap = len(terms & control_tokens)
            if semantic_overlap == 0 and control_overlap == 0:
                continue

            semantic_score = semantic_overlap / max(1, len(terms))
            control_score = control_overlap / max(1, len(terms))
            degree_bonus = min(0.2, self._degree_index.get(node_id, 0) / 30.0)
            fused_score = (
                semantic_score * self.semantic_weight
                + control_score * self.control_weight
                + degree_bonus
            )
            scores.append((node_id, fused_score, semantic_score, control_score))

        scores.sort(key=lambda item: item[1], reverse=True)
        return scores[: max(1, top_k)]

    def _merge_candidates(
        self,
        *,
        semantic_candidates: list[tuple[str, float, str]],
        control_candidates: list[tuple[str, float, float, float]],
        limit: int,
    ) -> list[tuple[str, float, float, float]]:
        merged: dict[str, dict[str, float]] = {}

        semantic_max = max([score for _, score, _ in semantic_candidates], default=1.0)
        if semantic_max <= 0:
            semantic_max = 1.0
        for node_id, score, _reason in semantic_candidates:
            item = merged.setdefault(node_id, {"semantic": 0.0, "control": 0.0, "fused": 0.0})
            item["semantic"] = max(item["semantic"], score / semantic_max)

        for node_id, fused_score, semantic_score, control_score in control_candidates:
            item = merged.setdefault(node_id, {"semantic": 0.0, "control": 0.0, "fused": 0.0})
            item["fused"] = max(item["fused"], fused_score)
            item["semantic"] = max(item["semantic"], semantic_score)
            item["control"] = max(item["control"], control_score)

        ranked: list[tuple[str, float, float, float]] = []
        for node_id, item in merged.items():
            fused_score = (
                item["fused"] * 0.5
                + item["semantic"] * self.semantic_weight * 0.4
                + item["control"] * self.control_weight * 0.4
            )
            ranked.append((node_id, fused_score, item["semantic"], item["control"]))

        ranked.sort(key=lambda row: row[1], reverse=True)
        return ranked[: max(1, limit)]

    def _upsert_node_merge(
        self,
        *,
        node_id: str,
        name: str,
        node_type: str,
        aliases: list[str],
        attributes: dict[str, Any],
    ) -> None:
        existing = self.store.nodes.get(node_id)
        merged_aliases: list[str] = []
        seen: set[str] = set()

        for alias in (existing.aliases if existing else []) + aliases:
            token = str(alias).strip()
            if not token:
                continue
            key = token.lower()
            if key in seen:
                continue
            seen.add(key)
            merged_aliases.append(token)

        merged_attributes = dict(existing.attributes) if existing else {}
        merged_attributes.update({k: v for k, v in attributes.items() if v is not None})

        self.store.upsert_node(
            node_id=node_id,
            name=existing.name if existing and existing.name else name,
            node_type=existing.node_type if existing and existing.node_type else node_type,
            aliases=merged_aliases,
            attributes=merged_attributes,
        )

    def _make_event_id(self, *, trace_id: str | None, summary: str, timestamp: str) -> str:
        if trace_id:
            normalized = "".join(ch for ch in trace_id.lower() if ch.isalnum() or ch in {"-", "_"})
            if normalized:
                return f"event:{normalized}"

        raw = f"{summary}|{timestamp}"
        digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:14]
        return f"event:{digest}"

    def _rebuild_dual_layer_index(self) -> None:
        self._semantic_index = {}
        self._control_index = {}
        self._degree_index = defaultdict(int)

        for edge in self.store.edges:
            self._degree_index[edge.source] += 1
            self._degree_index[edge.target] += 1

        for node_id, node in self.store.nodes.items():
            semantic_tokens: set[str] = set()
            control_tokens: set[str] = set()

            semantic_tokens.update(tokenize(node.node_id))
            semantic_tokens.update(tokenize(node.name))
            for alias in node.aliases:
                semantic_tokens.update(tokenize(alias))
            for key, value in node.attributes.items():
                semantic_tokens.update(tokenize(str(key)))
                semantic_tokens.update(tokenize(str(value)))

            control_tokens.update(tokenize(node.node_type))
            degree = self._degree_index.get(node_id, 0)
            control_tokens.add(f"degree_{min(degree, 8)}")
            if degree >= 4:
                control_tokens.add("hub_node")

            self._semantic_index[node_id] = {token for token in semantic_tokens if token}
            self._control_index[node_id] = {token for token in control_tokens if token}

        for edge in self.store.edges:
            src_tokens = self._control_index.setdefault(edge.source, set())
            tgt_tokens = self._control_index.setdefault(edge.target, set())
            relation_tokens = tokenize(edge.relation)
            for token in relation_tokens:
                src_tokens.add(token)
                tgt_tokens.add(token)
                src_tokens.add(f"out_{token}")
                tgt_tokens.add(f"in_{token}")

            src_node = self.store.nodes.get(edge.source)
            tgt_node = self.store.nodes.get(edge.target)
            if src_node is not None and tgt_node is not None:
                src_tokens.add(f"to_{tgt_node.node_type.lower()}")
                tgt_tokens.add(f"to_{src_node.node_type.lower()}")

    def _collect_relation_terms(self, *, node_id: str, hops: int, limit: int) -> set[str]:
        terms: set[str] = set()
        for line in self._collect_relation_lines(node_id=node_id, hops=hops, max_lines=limit):
            for token in tokenize(line):
                if len(token) > 2:
                    terms.add(token)
                if len(terms) >= limit:
                    return terms
        return terms

    def _collect_relation_lines(self, *, node_id: str, hops: int, max_lines: int = 32) -> list[str]:
        if hops <= 0:
            return []

        lines: list[str] = []
        line_set: set[str] = set()
        frontier = {node_id}
        visited = {node_id}

        for _ in range(hops):
            next_frontier: set[str] = set()
            for current in frontier:
                for edge in self.store.neighbors(current):
                    other = edge.target if edge.source == current else edge.source
                    src_name = self.store.nodes.get(edge.source).name if edge.source in self.store.nodes else edge.source
                    tgt_name = self.store.nodes.get(edge.target).name if edge.target in self.store.nodes else edge.target
                    rel_line = f"{src_name} -[{edge.relation}]-> {tgt_name}"
                    if rel_line not in line_set:
                        line_set.add(rel_line)
                        lines.append(rel_line)
                        if len(lines) >= max_lines:
                            return lines
                    if other not in visited:
                        visited.add(other)
                        next_frontier.add(other)
            frontier = next_frontier
            if not frontier:
                break

        return lines

    def _bfs_distances(self, *, seed_id: str, depth: int) -> dict[str, int]:
        if depth <= 0:
            return {seed_id: 0}

        distances: dict[str, int] = {seed_id: 0}
        frontier = {seed_id}

        for level in range(1, depth + 1):
            next_frontier: set[str] = set()
            for current in frontier:
                for edge in self.store.neighbors(current):
                    other = edge.target if edge.source == current else edge.source
                    if other in distances:
                        continue
                    distances[other] = level
                    next_frontier.add(other)
            frontier = next_frontier
            if not frontier:
                break

        return distances

    def _compute_gain(
        self,
        *,
        previous_scores: dict[str, float],
        current_scores: dict[str, float],
        focus_nodes: list[str],
    ) -> float:
        nodes = set(focus_nodes)
        if not nodes:
            return 0.0

        prev_total = sum(max(previous_scores.get(node_id, 0.0), 0.0) for node_id in nodes)
        delta_total = sum(
            max(current_scores.get(node_id, 0.0) - previous_scores.get(node_id, 0.0), 0.0)
            for node_id in nodes
        )

        if prev_total <= 1e-9:
            return float(delta_total)
        return float(delta_total / prev_total)
