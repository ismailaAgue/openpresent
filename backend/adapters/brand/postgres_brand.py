"""Postgres-backed Brand Profile adapter — same BrandProfilePort
contract as SqliteBrandAdapter. Same connection-pool pattern as the
other Postgres adapters (ADR-019)."""

import time
from psycopg2 import pool as pg_pool
from backend.ports.brand import BrandProfilePort, BrandProfile


class PostgresBrandAdapter(BrandProfilePort):
    def __init__(self, database_url: str):
        self._pool = pg_pool.ThreadedConnectionPool(1, 5, database_url)
        self._ensure_schema()

    def _ensure_schema(self):
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS op_brand_profiles (
                        workspace_id TEXT PRIMARY KEY,
                        owner_id TEXT NOT NULL,
                        name TEXT NOT NULL DEFAULT '',
                        colors TEXT NOT NULL DEFAULT '',
                        tone TEXT NOT NULL DEFAULT '',
                        audience TEXT NOT NULL DEFAULT '',
                        visual_style TEXT NOT NULL DEFAULT '',
                        created_at DOUBLE PRECISION NOT NULL,
                        updated_at DOUBLE PRECISION NOT NULL
                    )
                """)
        finally:
            self._pool.putconn(conn)

    def set_brand_profile(self, workspace_id: str, owner_id: str, name: str = "", colors: str = "",
                           tone: str = "", audience: str = "", visual_style: str = "") -> BrandProfile:
        now = time.time()
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT created_at FROM op_brand_profiles WHERE workspace_id = %s AND owner_id = %s",
                    (workspace_id, owner_id),
                )
                existing = cur.fetchone()
                created_at = existing[0] if existing else now
                cur.execute(
                    """
                    INSERT INTO op_brand_profiles (workspace_id, owner_id, name, colors, tone, audience,
                                                    visual_style, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (workspace_id) DO UPDATE SET
                        name = excluded.name, colors = excluded.colors, tone = excluded.tone,
                        audience = excluded.audience, visual_style = excluded.visual_style,
                        updated_at = excluded.updated_at
                    """,
                    (workspace_id, owner_id, name, colors, tone, audience, visual_style, created_at, now),
                )
        finally:
            self._pool.putconn(conn)
        return BrandProfile(workspace_id=workspace_id, owner_id=owner_id, name=name, colors=colors,
                             tone=tone, audience=audience, visual_style=visual_style,
                             created_at=created_at, updated_at=now)

    def get_brand_profile(self, workspace_id: str, owner_id: str) -> BrandProfile | None:
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT workspace_id, owner_id, name, colors, tone, audience, visual_style, "
                    "created_at, updated_at FROM op_brand_profiles WHERE workspace_id = %s AND owner_id = %s",
                    (workspace_id, owner_id),
                )
                row = cur.fetchone()
        finally:
            self._pool.putconn(conn)
        if row is None:
            return None
        return BrandProfile(workspace_id=row[0], owner_id=row[1], name=row[2], colors=row[3],
                             tone=row[4], audience=row[5], visual_style=row[6],
                             created_at=row[7], updated_at=row[8])

    def delete_brand_profile(self, workspace_id: str, owner_id: str) -> bool:
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM op_brand_profiles WHERE workspace_id = %s AND owner_id = %s",
                    (workspace_id, owner_id),
                )
                return cur.rowcount > 0
        finally:
            self._pool.putconn(conn)
