from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Any
import uuid


@dataclass(slots=True)
class VersionRecord:
    version_id: str
    label: str
    created_at: str
    snapshot_path: str
    metadata: dict[str, Any]
    parent_version_id: str | None = None
    thread_id: str = "global"
    branch: str = "main"


class SqliteVersionStore:
    def __init__(self, *, db_path: str | Path, version_dir: str | Path) -> None:
        self.db_path = Path(db_path)
        self.version_dir = Path(version_dir)
        self.version_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.version_dir / "versions_index.json"
        self._records: list[VersionRecord] = []
        self._heads: dict[str, dict[str, str]] = {}
        self._load()

    def create_version(
        self,
        *,
        label: str,
        metadata: dict[str, Any] | None = None,
        thread_id: str = "global",
        branch: str = "main",
        parent_version_id: str | None = None,
    ) -> VersionRecord:
        if not self.db_path.exists():
            raise FileNotFoundError(f"database not found: {self.db_path}")

        normalized_thread = thread_id.strip() or "global"
        normalized_branch = branch.strip() or "main"
        parent = parent_version_id or self.get_head(thread_id=normalized_thread, branch=normalized_branch)

        version_id = str(uuid.uuid4())
        snapshot_path = self.version_dir / f"{version_id}.db"
        shutil.copy2(self.db_path, snapshot_path)

        record = VersionRecord(
            version_id=version_id,
            label=label,
            created_at=datetime.now(timezone.utc).isoformat(),
            snapshot_path=str(snapshot_path),
            metadata=dict(metadata or {}),
            parent_version_id=parent,
            thread_id=normalized_thread,
            branch=normalized_branch,
        )
        self._records.append(record)
        self._set_head(normalized_thread, normalized_branch, version_id)
        self._save()
        return record

    def list_versions(
        self,
        limit: int = 50,
        *,
        thread_id: str | None = None,
        branch: str | None = None,
    ) -> list[VersionRecord]:
        values = self._records
        if thread_id:
            values = [v for v in values if v.thread_id == thread_id]
        if branch:
            values = [v for v in values if v.branch == branch]
        return list(reversed(values))[:limit]

    def list_tree(self, *, thread_id: str, limit: int = 200) -> tuple[list[VersionRecord], dict[str, str]]:
        nodes = [v for v in self._records if v.thread_id == thread_id]
        if limit > 0:
            nodes = nodes[-limit:]
        heads = self.list_branch_heads(thread_id=thread_id)
        return nodes, heads

    def list_branch_heads(self, *, thread_id: str) -> dict[str, str]:
        return {
            branch: version_id
            for branch, version_id in self._heads.get(thread_id, {}).items()
            if version_id
        }

    def get_head(self, *, thread_id: str, branch: str) -> str | None:
        value = self._heads.get(thread_id, {}).get(branch)
        return value or None

    def create_branch(
        self,
        *,
        thread_id: str,
        branch: str,
        from_version_id: str | None = None,
        from_branch: str = "main",
    ) -> str | None:
        normalized_thread = thread_id.strip() or "global"
        normalized_branch = branch.strip() or "main"
        if normalized_thread not in self._heads:
            self._heads[normalized_thread] = {}

        if normalized_branch in self._heads[normalized_thread]:
            raise ValueError(f"branch already exists: {normalized_branch}")

        source_version_id = from_version_id
        if source_version_id is None:
            source_version_id = self.get_head(thread_id=normalized_thread, branch=from_branch)

        if source_version_id and self.get_version(source_version_id) is None:
            raise ValueError(f"source version not found: {source_version_id}")

        if source_version_id:
            self._set_head(normalized_thread, normalized_branch, source_version_id)
        else:
            self._heads[normalized_thread][normalized_branch] = ""
        self._save()
        return source_version_id

    def rollback(
        self,
        version_id: str,
        *,
        thread_id: str | None = None,
        branch: str | None = None,
    ) -> VersionRecord:
        record = self.get_version(version_id)
        if record is None:
            raise ValueError(f"version not found: {version_id}")

        snapshot_path = Path(record.snapshot_path)
        if not snapshot_path.exists():
            raise FileNotFoundError(f"snapshot missing: {snapshot_path}")

        shutil.copy2(snapshot_path, self.db_path)
        target_thread = thread_id or record.thread_id
        target_branch = branch or record.branch
        self._set_head(target_thread, target_branch, version_id)
        self._save()
        return record

    def get_version(self, version_id: str) -> VersionRecord | None:
        for record in self._records:
            if record.version_id == version_id:
                return record
        return None

    def _load(self) -> None:
        if not self.index_file.exists():
            self._records = []
            self._heads = {}
            return

        payload = json.loads(self.index_file.read_text(encoding="utf-8"))
        normalized_records: list[VersionRecord] = []
        for item in payload.get("versions", []):
            item.setdefault("parent_version_id", None)
            item.setdefault("thread_id", "global")
            item.setdefault("branch", "main")
            item.setdefault("metadata", {})
            normalized_records.append(VersionRecord(**item))
        self._records = normalized_records

        raw_heads = payload.get("heads", {})
        if isinstance(raw_heads, dict):
            normalized_heads: dict[str, dict[str, str]] = {}
            for thread_id, branch_map in raw_heads.items():
                if isinstance(branch_map, dict):
                    normalized_heads[thread_id] = {
                        str(branch_name): str(version_id)
                        for branch_name, version_id in branch_map.items()
                        if version_id is not None
                    }
            self._heads = normalized_heads
        else:
            self._heads = {}

        if not self._heads:
            self._rebuild_heads_from_records()

    def _save(self) -> None:
        payload = {
            "versions": [asdict(v) for v in self._records],
            "heads": self._heads,
        }
        self.index_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _set_head(self, thread_id: str, branch: str, version_id: str) -> None:
        normalized_thread = thread_id.strip() or "global"
        normalized_branch = branch.strip() or "main"
        if normalized_thread not in self._heads:
            self._heads[normalized_thread] = {}
        self._heads[normalized_thread][normalized_branch] = version_id

    def _rebuild_heads_from_records(self) -> None:
        self._heads = {}
        for record in self._records:
            self._set_head(record.thread_id, record.branch, record.version_id)
