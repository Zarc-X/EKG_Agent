from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.models import (
    EvidenceItem,
    KnowledgeIncrementalUpdateRequest,
    KnowledgeIncrementalUpdateResponse,
    KnowledgeIndexRebuildResponse,
    KnowledgeSearchResponse,
)
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


@router.post("/knowledge/index/rebuild", response_model=KnowledgeIndexRebuildResponse)
def rebuild_knowledge_index(
    graph_rag: GraphRAGService = Depends(get_graph_rag),
) -> KnowledgeIndexRebuildResponse:
    stats = graph_rag.refresh_index()
    return KnowledgeIndexRebuildResponse(status="ok", **stats)


@router.post("/knowledge/incremental-update", response_model=KnowledgeIncrementalUpdateResponse)
def incremental_update_knowledge(
    request: KnowledgeIncrementalUpdateRequest,
    graph_rag: GraphRAGService = Depends(get_graph_rag),
) -> KnowledgeIncrementalUpdateResponse:
    try:
        result = graph_rag.apply_ontology_incremental_update(
            thread_id=request.thread_id,
            branch=request.branch,
            user_id=request.user_id,
            trace_id=request.trace_id,
            change_log={
                "operation_type": request.operation_type,
                "summary": request.summary,
                "sql": request.sql,
                "params": request.params,
                "touched_tables": request.touched_tables,
                "rowcount": request.rowcount,
            },
            version_id=request.version_id,
            parent_version_id=request.parent_version_id,
            recorded_at=request.recorded_at.isoformat() if request.recorded_at else None,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"incremental update failed: {exc}") from exc

    return KnowledgeIncrementalUpdateResponse(
        status=str(result.get("status", "updated")),
        event_id=result.get("event_id"),
        tables=[str(item) for item in result.get("tables", [])],
        index={
            k: int(v)
            for k, v in (result.get("index") or {}).items()
        },
        reason=result.get("reason"),
    )
