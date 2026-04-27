from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.models import EvidenceItem, KnowledgeSearchResponse
from app.knowledge import GraphRAGService, OntologyStore, seed_default_ontology

from ..dependencies import get_graph_rag, get_ontology_store

router = APIRouter(tags=["knowledge"])


@router.post("/knowledge/bootstrap")
def bootstrap_knowledge(store: OntologyStore = Depends(get_ontology_store)) -> dict[str, str]:
    seed_default_ontology(store)
    return {"status": "ok", "message": "ontology bootstrapped"}


@router.get("/knowledge/search", response_model=KnowledgeSearchResponse)
def search_knowledge(
    q: str,
    top_k: int = 5,
    graph_rag: GraphRAGService = Depends(get_graph_rag),
) -> KnowledgeSearchResponse:
    result = graph_rag.retrieve(query=q, top_k=top_k, hops=1)
    evidence = [
        EvidenceItem(
            node_id=e.node_id,
            title=e.title,
            score=e.score,
            relation_summary=e.relation_summary,
        )
        for e in result.evidence
    ]
    return KnowledgeSearchResponse(query=q, context=result.context, evidence=evidence)
