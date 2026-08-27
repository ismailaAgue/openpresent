"""Postgres-backed Workspace adapter — same WorkspacePort contract as
SqliteWorkspaceAdapter, persists across web service restarts. Same
connection-pool pattern as the other Postgres adapters (ADR-019)."""

import time
import uuid
from psycopg2 import pool as pg_pool
from backend.ports.workspace import WorkspacePort, WorkspaceSummary


class PostgresWorkspaceAdapter(WorkspacePort):
    def __init__(self, database_url: str):
        self._pool = pg_pool.ThreadedConnectionPool(1, 5, database_url)
        self._ensure_schema()

    def _ensure_schema(self):
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS op_workspaces (
                        id TEXT PRIMARY KEY,
                        owner_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                        created_at DOUBLE PRECISION NOT NULL,
                        updated_at DOUBLE PRECISION NOT NULL
                    )
                """)
        finally:
            self._pool.putconn(conn)

    def create_workspace(self, owner_id: str, name: str) -> str:
        workspace_id = str(uuid.uuid4())
        now = time.time()
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO op_workspaces (id, owner_id, name, created_at, updated_at) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (workspace_id, owner_id, name, now, now),
                )
        finally:
            self._pool.putconn(conn)
        return workspace_id

    def get_workspace(self, workspace_id: str, owner_id: str) -> WorkspaceSummary | None:
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, owner_id, name, created_at, updated_at FROM op_workspaces "
                    "WHERE id = %s AND owner_id = %s",
                    (workspace_id, owner_id),
                )
                row = cur.fetchone()
        finally:
            self._pool.putconn(conn)
        if row is None:
            return None
        return WorkspaceSummary(workspace_id=row[0], owner_id=row[1], name=row[2], created_at=row[3], updated_at=row[4])

    def list_workspaces(self, owner_id: str) -> list[WorkspaceSummary]:
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, owner_id, name, created_at, updated_at FROM op_workspaces "
                    "WHERE owner_id = %s ORDER BY updated_at DESC",
                    (owner_id,),
                )
                rows = cur.fetchall()
        finally:
            self._pool.putconn(conn)
        return [
            WorkspaceSummary(workspace_id=r[0], owner_id=r[1], name=r[2], created_at=r[3], updated_at=r[4])
            for r in rows
        ]

    def rename_workspace(self, workspace_id: str, owner_id: str, name: str) -> bool:
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE op_workspaces SET name = %s, updated_at = %s WHERE id = %s AND owner_id = %s",
                    (name, time.time(), workspace_id, owner_id),
                )
                return cur.rowcount > 0
        finally:
            self._pool.putconn(conn)

    def delete_workspace(self, workspace_id: str, owner_id: str) -> bool:
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM op_workspaces WHERE id = %s AND owner_id = %s",
                    (workspace_id, owner_id),
                )
                return cur.rowcount > 0
        finally:
            self._pool.putconn(conn)
