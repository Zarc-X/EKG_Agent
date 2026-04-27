from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sqlite3
import tempfile
from typing import Any, Iterator


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ComponentRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize_schema(self) -> None:
        with self.connection() as conn:
            conn.executescript(
                """
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS components (
                    part_number TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    category TEXT,
                    package TEXT,
                    voltage TEXT,
                    current TEXT,
                    manufacturer TEXT,
                    purchase_date TEXT,
                    purchase_id TEXT,
                    description TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS inventory (
                    part_number TEXT PRIMARY KEY,
                    quantity INTEGER NOT NULL DEFAULT 0,
                    location TEXT,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (part_number) REFERENCES components(part_number)
                );

                CREATE TABLE IF NOT EXISTS bom (
                    parent_part_number TEXT NOT NULL,
                    child_part_number TEXT NOT NULL,
                    qty REAL NOT NULL,
                    PRIMARY KEY (parent_part_number, child_part_number),
                    FOREIGN KEY (parent_part_number) REFERENCES components(part_number),
                    FOREIGN KEY (child_part_number) REFERENCES components(part_number)
                );
                """
            )
            self._ensure_component_columns(conn)

    def _ensure_component_columns(self, conn: sqlite3.Connection) -> None:
        existing = {
            str(row["name"])
            for row in conn.execute("PRAGMA table_info(components)")
        }

        required_columns = {
            "manufacturer": "TEXT",
            "purchase_date": "TEXT",
            "purchase_id": "TEXT",
        }

        for name, col_type in required_columns.items():
            if name in existing:
                continue
            conn.execute(f'ALTER TABLE components ADD COLUMN "{name}" {col_type}')

    def seed_sample_data(self) -> None:
        now = _utc_now()
        with self.connection() as conn:
            conn.executemany(
                """
                INSERT OR IGNORE INTO components
                (part_number, name, category, package, voltage, current, manufacturer, purchase_date, purchase_id, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "STM32F103C8T6",
                        "STM32F103 MCU",
                        "MCU",
                        "LQFP48",
                        "3.3V",
                        "20mA",
                        "STMicroelectronics",
                        "",
                        "",
                        "32-bit ARM Cortex-M3 microcontroller",
                        now,
                        now,
                    ),
                    (
                        "TPS5430",
                        "TI Buck Converter",
                        "PMIC",
                        "SOIC8",
                        "5V-36V",
                        "3A",
                        "Texas Instruments",
                        "",
                        "",
                        "Step-down DC/DC converter",
                        now,
                        now,
                    ),
                ],
            )
            conn.executemany(
                """
                INSERT OR IGNORE INTO inventory
                (part_number, quantity, location, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                [
                    ("STM32F103C8T6", 240, "A1-R2", now),
                    ("TPS5430", 120, "B3-R1", now),
                ],
            )

    def execute_sql(self, sql: str, params: tuple[Any, ...] | list[Any] | None = None) -> dict[str, Any]:
        with self.connection() as conn:
            return self._execute_on_connection(conn, sql, params)

    def simulate_sql(self, sql: str, params: tuple[Any, ...] | list[Any] | None = None) -> dict[str, Any]:
        if not self.db_path.exists():
            raise FileNotFoundError(f"database not found: {self.db_path}")

        with tempfile.TemporaryDirectory(prefix="ekg_sql_sandbox_") as td:
            sandbox_db = Path(td) / "sandbox.db"
            shutil.copy2(self.db_path, sandbox_db)

            conn = sqlite3.connect(sandbox_db)
            conn.row_factory = sqlite3.Row
            try:
                result = self._execute_on_connection(conn, sql, params)
                conn.rollback()
                return result
            finally:
                conn.close()

    def list_tables(self) -> list[str]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                ORDER BY name
                """
            ).fetchall()
        return [str(r[0]) for r in rows]

    def _execute_on_connection(
        self,
        conn: sqlite3.Connection,
        sql: str,
        params: tuple[Any, ...] | list[Any] | None = None,
    ) -> dict[str, Any]:
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        if not statements:
            return {"message": "empty sql", "rows": [], "columns": [], "rowcount": 0}

        last_cur: sqlite3.Cursor | None = None
        for stmt in statements:
            last_cur = conn.execute(stmt, tuple(params or ()))

        assert last_cur is not None
        if last_cur.description is None:
            return {
                "message": "ok",
                "rows": [],
                "columns": [],
                "rowcount": max(last_cur.rowcount, 0),
            }

        rows = [dict(r) for r in last_cur.fetchmany(200)]
        cols = [d[0] for d in last_cur.description]
        return {
            "message": "ok",
            "rows": rows,
            "columns": cols,
            "rowcount": len(rows),
        }

    def list_part_numbers(self, limit: int | None = None) -> list[str]:
        sql = "SELECT part_number FROM components WHERE part_number IS NOT NULL AND part_number <> '' ORDER BY part_number"
        if limit is not None and limit > 0:
            sql += " LIMIT ?"

        with self.connection() as conn:
            if limit is not None and limit > 0:
                rows = conn.execute(sql, (limit,)).fetchall()
            else:
                rows = conn.execute(sql).fetchall()
        return [str(r[0]) for r in rows if r[0] not in (None, "")]

    def list_manufacturers(self, limit: int | None = None) -> list[str]:
        sql = (
            "SELECT DISTINCT manufacturer FROM components "
            "WHERE manufacturer IS NOT NULL AND manufacturer <> '' ORDER BY manufacturer"
        )
        if limit is not None and limit > 0:
            sql += " LIMIT ?"

        with self.connection() as conn:
            if limit is not None and limit > 0:
                rows = conn.execute(sql, (limit,)).fetchall()
            else:
                rows = conn.execute(sql).fetchall()
        return [str(r[0]) for r in rows if r[0] not in (None, "")]
