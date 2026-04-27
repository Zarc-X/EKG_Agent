from __future__ import annotations

from pathlib import Path
import logging

from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import admin_router, approval_router, chat_router, knowledge_router
from app.bootstrap import bootstrap_from_excel
from app.codegen import ComponentCodeGenerator
from app.config import get_settings
from app.core.approval import ApprovalService
from app.core.safe_agent_llm import build_safe_agent_callback
from app.core.security_runtime import load_security_bundle
from app.core.workflow import UnifiedWorkflowService
from app.db import ComponentRepository, SqlSandboxPolicy, SqliteVersionStore
from app.knowledge import EntityLinker, GraphRAGService, OntologyStore, seed_default_ontology
from app.llm import OpenAICompatLLMClient, OpenAICompatLLMClientConfig
from app.web_ui import render_home_html


logger = logging.getLogger(__name__)


def _resolve_path(project_root: Path, raw: str) -> Path:
    p = Path(raw)
    if p.is_absolute():
        return p
    return (project_root / p).resolve()


def create_app() -> FastAPI:
    app = FastAPI(title="EKG Agent Refactor")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    settings = get_settings()
    project_root = Path(__file__).resolve().parents[1]

    db_path = _resolve_path(project_root, settings.sqlite_db_path)
    ontology_path = _resolve_path(project_root, settings.ontology_json_path)
    version_dir = _resolve_path(project_root, settings.version_dir)
    audit_log = _resolve_path(project_root, settings.security_audit_log)

    version_dir.mkdir(parents=True, exist_ok=True)
    ontology_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    audit_log.parent.mkdir(parents=True, exist_ok=True)

    ontology_store = OntologyStore(json_path=ontology_path)
    ontology_store.load()
    component_repo = ComponentRepository(db_path=db_path)
    component_repo.initialize_schema()

    excel_bootstrapped = False
    excel_path = _resolve_path(project_root, settings.excel_file_path)
    if settings.excel_bootstrap_enabled and excel_path.exists():
        try:
            result = bootstrap_from_excel(
                excel_path=excel_path,
                repo=component_repo,
                ontology_store=ontology_store,
            )
            excel_bootstrapped = result.total_rows > 0
            logger.info(
                "Excel bootstrap done. sheets=%s rows=%s components=%s",
                result.sheet_count,
                result.total_rows,
                result.component_count,
            )
        except Exception:
            logger.exception("Excel bootstrap failed, fallback to default seed.")

    if not excel_bootstrapped:
        seed_default_ontology(ontology_store)
        component_repo.seed_sample_data()

    version_store = SqliteVersionStore(db_path=db_path, version_dir=version_dir)

    llm_client = None
    if settings.llm_enabled and settings.llm_api_key and settings.llm_model:
        llm_client = OpenAICompatLLMClient(
            OpenAICompatLLMClientConfig(
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                model=settings.llm_model,
                timeout_s=settings.llm_timeout_s,
                temperature=settings.llm_temperature,
            )
        )

    safe_agent_callback = None
    if llm_client is not None and settings.llm_use_for_safe_agent:
        safe_agent_callback = build_safe_agent_callback(llm_client)

    security_bundle = load_security_bundle(
        audit_log_path=str(audit_log),
        secret_key=settings.security_secret,
        safe_agent_callback=safe_agent_callback,
    )

    graph_rag = GraphRAGService(
        store=ontology_store,
        linker=EntityLinker(ontology_store),
        iterations=settings.graph_rag_iterations,
        iteration_top_k=settings.graph_rag_iteration_top_k,
        max_query_terms=settings.graph_rag_max_query_terms,
        semantic_weight=settings.graph_rag_semantic_weight,
        control_weight=settings.graph_rag_control_weight,
        adaptive_stop_enabled=settings.graph_rag_adaptive_stop_enabled,
        adaptive_min_gain=settings.graph_rag_adaptive_min_gain,
        adaptive_min_new_nodes=settings.graph_rag_adaptive_min_new_nodes,
        adaptive_stable_rounds=settings.graph_rag_adaptive_stable_rounds,
    )

    part_number_vocab = component_repo.list_part_numbers()
    manufacturer_vocab = component_repo.list_manufacturers()

    workflow = UnifiedWorkflowService(
        graph_rag=graph_rag,
        codegen=ComponentCodeGenerator(
            llm_client=llm_client,
            part_number_vocab=part_number_vocab,
            manufacturer_vocab=manufacturer_vocab,
        ),
        repo=component_repo,
        versions=version_store,
        approval=ApprovalService(),
        security=security_bundle,
        sql_sandbox=SqlSandboxPolicy(max_statements=settings.sql_sandbox_max_statements),
        sandbox_enabled=settings.sql_sandbox_enabled,
        top_k=settings.graph_rag_top_k,
    )

    app.state.workflow = workflow
    app.state.ontology_store = ontology_store
    app.state.graph_rag = graph_rag

    api_prefix = "/v1"
    app.include_router(chat_router, prefix=api_prefix)
    app.include_router(approval_router, prefix=api_prefix)
    app.include_router(knowledge_router, prefix=api_prefix)
    app.include_router(admin_router, prefix=api_prefix)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return render_home_html()

    @app.get("/status")
    def status() -> dict[str, str]:
        return {
            "service": settings.app_name,
            "status": "running",
            "docs": "/docs",
            "health": "/health",
            "api_prefix": api_prefix,
        }

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon() -> Response:
        return Response(status_code=204)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": settings.app_name}

    return app


app = create_app()
