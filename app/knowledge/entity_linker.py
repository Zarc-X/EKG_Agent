from __future__ import annotations

import re

from .ontology_store import OntologyStore


_TOKEN_RE = re.compile(r"[A-Za-z0-9_\-\u4e00-\u9fff]+")


def tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in _TOKEN_RE.finditer(text or "")]


class EntityLinker:
    def __init__(self, store: OntologyStore) -> None:
        self.store = store

    def link(self, query: str, top_k: int = 5) -> list[tuple[str, float, str]]:
        terms = tokenize(query)
        if not terms:
            return []

        matched = self.store.search_nodes(terms, top_k=top_k)
        results: list[tuple[str, float, str]] = []
        for node, score in matched:
            reason = f"term overlap match on node '{node.name}'"
            results.append((node.node_id, score, reason))
        return results
