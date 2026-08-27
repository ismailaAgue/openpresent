"""SQLite implementation of BrandProfilePort (ADR-045). Same pattern
as the other adapters — dev/local here, Postgres in prod."""

import sqlite3
import time
from backend.ports.brand import BrandProfilePort, BrandProfile


class SqliteBrandAdapter(BrandProfilePort):
    def __init__(self, db_path: str = ":memory:"):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS brand_profiles (
                workspace_id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                name TEXT NOT NULL DEFAULT '',
                colors TEXT NOT NULL DEFAULT '',
                tone TEXT NOT NULL DEFAULT '',
                audience TEXT NOT NULL DEFAULT '',
                visual_style TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        self._conn.commit()

    def set_brand_profile(self, workspace_id: str, owner_id: str, name: str = "", colors: str = "",
                           tone: str = "", audience: str = "", visual_style: str = "") -> BrandProfile:
        now = time.time()
        existing = self._conn.execute(
            "SELECT created_at FROM brand_profiles WHERE workspace_id = ? AND owner_id = ?",
            (workspace_id, owner_id),
        ).fetchone()
        created_at = existing[0] if existing else now
        self._conn.execute(
            """
            INSERT INTO brand_profiles (workspace_id, owner_id, name, colors, tone, audience, visual_style,
                                         created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(workspace_id) DO UPDATE SET
                name = excluded.name, colors = excluded.colors, tone = excluded.tone,
                audience = excluded.audience, visual_style = excluded.visual_style,
                updated_at = excluded.updated_at
            """,
            (workspace_id, owner_id, name, colors, tone, audience, visual_style, created_at, now),
        )
        self._conn.commit()
        return BrandProfile(workspace_id=workspace_id, owner_id=owner_id, name=name, colors=colors,
                             tone=tone, audience=audience, visual_style=visual_style,
                             created_at=created_at, updated_at=now)

    def get_brand_profile(self, workspace_id: str, owner_id: str) -> BrandProfile | None:
        row = self._conn.execute(
            "SELECT workspace_id, owner_id, name, colors, tone, audience, visual_style, created_at, updated_at "
            "FROM brand_profiles WHERE workspace_id = ? AND owner_id = ?",
            (workspace_id, owner_id),
        ).fetchone()
        if row is None:
            return None
        return BrandProfile(workspace_id=row[0], owner_id=row[1], name=row[2], colors=row[3],
                             tone=row[4], audience=row[5], visual_style=row[6],
                             created_at=row[7], updated_at=row[8])

    def delete_brand_profile(self, workspace_id: str, owner_id: str) -> bool:
        cur = self._conn.execute(
            "DELETE FROM brand_profiles WHERE workspace_id = ? AND owner_id = ?",
            (workspace_id, owner_id),
        )
        self._conn.commit()
        return cur.rowcount > 0
