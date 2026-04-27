from __future__ import annotations

from fastapi import Request

from app.core.workflow import UnifiedWorkflowService
from app.knowledge import GraphRAGService, OntologyStore


def get_workflow(request: Request) -> UnifiedWorkflowService:
    return request.app.state.workflow


def get_ontology_store(request: Request) -> OntologyStore:
    return request.app.state.ontology_store


def get_graph_rag(request: Request) -> GraphRAGService:
    return request.app.state.graph_rag
