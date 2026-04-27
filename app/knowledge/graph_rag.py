from __future__ import annotations

from dataclasses import dataclass

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
    def __init__(self, store: OntologyStore, linker: EntityLinker) -> None:
        self.store = store
        self.linker = linker

    def retrieve(self, query: str, top_k: int = 5, hops: int = 1) -> GraphRAGResult:
        linked = self.linker.link(query, top_k=top_k)
        evidence: list[GraphEvidence] = []
        context_lines: list[str] = []

        for node_id, score, _reason in linked:
            node = self.store.nodes.get(node_id)
            if node is None:
                continue

            relations = self._collect_relation_lines(node_id=node_id, hops=hops)
            relation_summary = " | ".join(relations[:3]) if relations else "no direct relation"

            evidence.append(
                GraphEvidence(
                    node_id=node.node_id,
                    title=node.name,
                    score=score,
                    relation_summary=relation_summary,
                )
            )
            context_lines.append(f"- {self.store.as_context_line(node.node_id)}")
            for rel in relations[:3]:
                context_lines.append(f"  - relation: {rel}")

        if not context_lines:
            tokens = tokenize(query)
            fallback = ", ".join(tokens[:8])
            context_lines.append(f"- no graph match, query tokens: {fallback}")

        return GraphRAGResult(context="\n".join(context_lines), evidence=evidence)

    def _collect_relation_lines(self, *, node_id: str, hops: int) -> list[str]:
        if hops <= 0:
            return []

        lines: list[str] = []
        frontier = {node_id}
        visited = {node_id}

        for _ in range(hops):
            next_frontier: set[str] = set()
            for current in frontier:
                for edge in self.store.neighbors(current):
                    other = edge.target if edge.source == current else edge.source
                    src_name = self.store.nodes.get(edge.source).name if edge.source in self.store.nodes else edge.source
                    tgt_name = self.store.nodes.get(edge.target).name if edge.target in self.store.nodes else edge.target
                    lines.append(f"{src_name} -[{edge.relation}]-> {tgt_name}")
                    if other not in visited:
                        visited.add(other)
                        next_frontier.add(other)
            frontier = next_frontier
            if not frontier:
                break

        return lines
