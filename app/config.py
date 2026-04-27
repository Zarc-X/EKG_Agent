from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "EKG Agent Refactor"
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8010

    data_dir: str = "./data"
    sqlite_db_path: str = "./data/components.db"
    ontology_json_path: str = "./data/ontology_graph.json"
    version_dir: str = "./data/versions"
    security_audit_log: str = "./data/audit/security_audit.jsonl"
    security_secret: str = "replace-with-strong-secret"

    graph_rag_top_k: int = 5

    sql_sandbox_enabled: bool = True
    sql_sandbox_max_statements: int = 8

    excel_bootstrap_enabled: bool = True
    excel_file_path: str = "../electronic_component_data.xlsx"

    llm_enabled: bool = True
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_api_key: str = ""
    llm_model: str = "qwen2.5-coder-7b-instruct"
    llm_timeout_s: float = 60.0
    llm_temperature: float = 0.1
    llm_use_for_safe_agent: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def ensure_dirs(self, project_root: Path) -> None:
        for raw in [self.data_dir, self.version_dir, self.security_audit_log]:
            p = (project_root / raw).resolve() if raw.startswith("./") else Path(raw).resolve()
            target = p.parent if p.suffix else p
            target.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
