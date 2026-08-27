"""SQLite implementation of WorkspacePort (ADR-044). Same pattern as
adapters/storage/sqlite_storage.py — dev/local here, Postgres in prod."""

import sqlite3
import time
import uuid
from backend.ports.workspace import WorkspacePort, WorkspaceSummary


class SqliteWorkspaceAdapter(WorkspacePort):
    def __init__(self, db_path: str = ":memory:"):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS workspaces (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                name TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        self._conn.commit()

    def create_workspace(self, owner_id: str, name: str) -> str:
        workspace_id = str(uuid.uuid4())
        now = time.time()
        self._conn.execute(
            "INSERT INTO workspaces (id, owner_id, name, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (workspace_id, owner_id, name, now, now),
        )
        self._conn.commit()
        return workspace_id

    def get_workspace(self, workspace_id: str, owner_id: str) -> WorkspaceSummary | None:
        row = self._conn.execute(
            "SELECT id, owner_id, name, created_at, updated_at FROM workspaces WHERE id = ? AND owner_id = ?",
            (workspace_id, owner_id),
        ).fetchone()
        if row is None:
            return None
        return WorkspaceSummary(workspace_id=row[0], owner_id=row[1], name=row[2], created_at=row[3], updated_at=row[4])

    def list_workspaces(self, owner_id: str) -> list[WorkspaceSummary]:
        rows = self._conn.execute(
            "SELECT id, owner_id, name, created_at, updated_at FROM workspaces "
            "WHERE owner_id = ? ORDER BY updated_at DESC",
            (owner_id,),
        ).fetchall()
        return [
            WorkspaceSummary(workspace_id=r[0], owner_id=r[1], name=r[2], created_at=r[3], updated_at=r[4])
            for r in rows
        ]

    def rename_workspace(self, workspace_id: str, owner_id: str, name: str) -> bool:
        cur = self._conn.execute(
            "UPDATE workspaces SET name = ?, updated_at = ? WHERE id = ? AND owner_id = ?",
            (name, time.time(), workspace_id, owner_id),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def delete_workspace(self, workspace_id: str, owner_id: str) -> bool:
        cur = self._conn.execute(
            "DELETE FROM workspaces WHERE id = ? AND owner_id = ?", (workspace_id, owner_id)
        )
        self._conn.commit()
        return cur.rowcount > 0
