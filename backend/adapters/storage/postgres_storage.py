"""
Postgres-backed Storage adapter — same StoragePort contract as
SqliteStorageAdapter, persists across web service restarts.

Revision (ADR-019): uses a connection pool, not a single shared
connection — see postgres_auth.py's module docstring for the full
reasoning (concurrent API request threads + the in-process worker
thread sharing one raw connection caused intermittent failures).
"""

import json
import time
import uuid
import dataclasses
from psycopg2 import pool as pg_pool
from backend.ports.storage import StoragePort, ProjectSummary
from backend.models.recipe import Recipe, Outline, Slide, ContentBlock, Theme, StructureSource, BlockType


class PostgresStorageAdapter(StoragePort):
    def __init__(self, database_url: str):
        self._pool = pg_pool.ThreadedConnectionPool(1, 5, database_url)
        self._ensure_schema()

    def _ensure_schema(self):
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS op_projects (
                        id TEXT PRIMARY KEY,
                        owner_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        recipe_json TEXT NOT NULL,
                        created_at DOUBLE PRECISION NOT NULL,
                        updated_at DOUBLE PRECISION NOT NULL
                    )
                """)
        finally:
            self._pool.putconn(conn)

    def save_recipe(self, owner_id: str, recipe: Recipe, title: str) -> str:
        project_id = recipe.project_id or str(uuid.uuid4())
        now = time.time()
        recipe_json = json.dumps(dataclasses.asdict(recipe))
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM op_projects WHERE id = %s AND owner_id = %s",
                    (project_id, owner_id),
                )
                existing = cur.fetchone()
                if existing:
                    cur.execute(
                        "UPDATE op_projects SET recipe_json = %s, title = %s, updated_at = %s WHERE id = %s",
                        (recipe_json, title, now, project_id),
                    )
                else:
                    cur.execute(
                        "INSERT INTO op_projects (id, owner_id, title, recipe_json, created_at, updated_at) "
                        "VALUES (%s, %s, %s, %s, %s, %s)",
                        (project_id, owner_id, title, recipe_json, now, now),
                    )
            return project_id
        finally:
            self._pool.putconn(conn)

    def get_recipe(self, project_id: str, owner_id: str) -> Recipe | None:
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT recipe_json FROM op_projects WHERE id = %s AND owner_id = %s",
                    (project_id, owner_id),
                )
                row = cur.fetchone()
        finally:
            self._pool.putconn(conn)
        if row is None:
            return None
        return _recipe_from_dict(json.loads(row[0]))

    def list_projects(self, owner_id: str) -> list[ProjectSummary]:
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, owner_id, title, created_at, updated_at FROM op_projects "
                    "WHERE owner_id = %s ORDER BY updated_at DESC",
                    (owner_id,),
                )
                rows = cur.fetchall()
        finally:
            self._pool.putconn(conn)
        return [
            ProjectSummary(project_id=r[0], owner_id=r[1], title=r[2], created_at=r[3], updated_at=r[4])
            for r in rows
        ]

    def delete_recipe(self, project_id: str, owner_id: str) -> bool:
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM op_projects WHERE id = %s AND owner_id = %s", (project_id, owner_id)
                )
                deleted = cur.rowcount > 0
            return deleted
        finally:
            self._pool.putconn(conn)


def _recipe_from_dict(d: dict) -> Recipe:
    outline_d = d["outline"]
    slides = [
        Slide(
            order=s["order"], title=s["title"],
            content_blocks=[
                ContentBlock(type=BlockType(b["type"]), text=b["text"], media_ref=b.get("media_ref"))
                for b in s["content_blocks"]
            ],
        ) for s in outline_d["slides"]
    ]
    outline = Outline(
        structure_source=StructureSource(outline_d["structure_source"]),
        slides=slides,
        document_type=outline_d.get("document_type", "general"),
    )
    theme = Theme(**d["theme"])
    return Recipe(
        recipe_version=d["recipe_version"], project_id=d["project_id"],
        source_text=d["source_text"], audience_type=d["audience_type"],
        language=d["language"], outline=outline, theme=theme,
    )
