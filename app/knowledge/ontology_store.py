from __future__ import annotations

from dataclasses import dataclass, asdict
import json
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class OntologyNode:
    node_id: str
    name: str
    node_type: str
    aliases: list[str]
    attributes: dict[str, Any]


@dataclass(slots=True)
class OntologyEdge:
    source: str
    target: str
    relation: str
    attributes: dict[str, Any]


class OntologyStore:
    def __init__(self, json_path: str | Path) -> None:
        self.json_path = Path(json_path)
        self.nodes: dict[str, OntologyNode] = {}
        self.edges: list[OntologyEdge] = []

    def load(self) -> None:
        if not self.json_path.exists():
            return

        payload = json.loads(self.json_path.read_text(encoding="utf-8"))
        self.nodes = {
            item["node_id"]: OntologyNode(**item) for item in payload.get("nodes", [])
        }
        self.edges = [OntologyEdge(**item) for item in payload.get("edges", [])]

    def save(self) -> None:
        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "nodes": [asdict(v) for v in self.nodes.values()],
            "edges": [asdict(v) for v in self.edges],
        }
        self.json_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def upsert_node(
        self,
        *,
        node_id: str,
        name: str,
        node_type: str,
        aliases: list[str] | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        self.nodes[node_id] = OntologyNode(
            node_id=node_id,
            name=name,
            node_type=node_type,
            aliases=aliases or [],
            attributes=attributes or {},
        )

    def add_edge(
        self,
        *,
        source: str,
        target: str,
        relation: str,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        edge = OntologyEdge(
            source=source,
            target=target,
            relation=relation,
            attributes=attributes or {},
        )
        if not self._has_same_edge(edge):
            self.edges.append(edge)

    def neighbors(self, node_id: str) -> list[OntologyEdge]:
        return [e for e in self.edges if e.source == node_id or e.target == node_id]

    def search_nodes(self, terms: list[str], top_k: int = 5) -> list[tuple[OntologyNode, float]]:
        scores: list[tuple[OntologyNode, float]] = []
        unique_terms = [t for t in {term.strip().lower() for term in terms} if t]
        if not unique_terms:
            return []

        for node in self.nodes.values():
            corpus = " ".join(
                [
                    node.node_id,
                    node.name,
                    " ".join(node.aliases),
                    " ".join([f"{k}:{v}" for k, v in node.attributes.items()]),
                ]
            ).lower()
            hit = 0.0
            for t in unique_terms:
                if t in corpus:
                    hit += 1.0
            if hit > 0:
                normalized = hit / max(len(unique_terms), 1)
                scores.append((node, round(normalized, 4)))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def as_context_line(self, node_id: str) -> str:
        node = self.nodes.get(node_id)
        if not node:
            return f"unknown node: {node_id}"
        attrs = ", ".join([f"{k}={v}" for k, v in node.attributes.items()])
        return f"[{node.node_type}] {node.name} ({node.node_id}) {attrs}".strip()

    def _has_same_edge(self, edge: OntologyEdge) -> bool:
        for e in self.edges:
            if e.source == edge.source and e.target == edge.target and e.relation == edge.relation:
                return True
        return False
