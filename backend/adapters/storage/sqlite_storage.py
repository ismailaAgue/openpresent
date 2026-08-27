"""
SQLite-backed Storage adapter — dev/local target. Production points at
managed Postgres per ADR-006; this adapter only speaks through
StoragePort, so that swap is a connection change, not a logic change.

Recipe is stored as JSON (dataclasses -> dict -> json), matching the
Blueprint Section 5 format. owner_id scoping happens in every query
here, not left to callers to remember (Blueprint Section 11 boundary).
"""

import json
import sqlite3
import time
import uuid
import dataclasses
from backend.ports.storage import StoragePort, ProjectSummary
from backend.models.recipe import Recipe, Outline, Slide, ContentBlock, Theme, StructureSource, BlockType


class SqliteStorageAdapter(StoragePort):
    def __init__(self, db_path: str = ":memory:"):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                title TEXT NOT NULL,
                recipe_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                workspace_id TEXT
            )
        """)
        self._conn.commit()
        self._ensure_workspace_id_column()  # ADR-044 — safe on pre-existing dev DBs too

    def _ensure_workspace_id_column(self):
        cols = [row[1] for row in self._conn.execute("PRAGMA table_info(projects)").fetchall()]
        if "workspace_id" not in cols:
            self._conn.execute("ALTER TABLE projects ADD COLUMN workspace_id TEXT")
            self._conn.commit()

    def save_recipe(self, owner_id: str, recipe: Recipe, title: str, workspace_id: str | None = None) -> str:
        project_id = recipe.project_id or str(uuid.uuid4())
        now = time.time()
        existing = self._conn.execute(
            "SELECT id FROM projects WHERE id = ? AND owner_id = ?", (project_id, owner_id)
        ).fetchone()
        recipe_json = json.dumps(_recipe_to_dict(recipe))
        if existing:
            # ADR-044: an update (re-save of an existing project, e.g.
            # after a slide edit) leaves workspace_id untouched unless
            # the caller explicitly passes one — editing a slide must
            # never silently un-assign a project from its workspace.
            if workspace_id is not None:
                self._conn.execute(
                    "UPDATE projects SET recipe_json = ?, title = ?, updated_at = ?, workspace_id = ? WHERE id = ?",
                    (recipe_json, title, now, workspace_id, project_id),
                )
            else:
                self._conn.execute(
                    "UPDATE projects SET recipe_json = ?, title = ?, updated_at = ? WHERE id = ?",
                    (recipe_json, title, now, project_id),
                )
        else:
            self._conn.execute(
                "INSERT INTO projects (id, owner_id, title, recipe_json, created_at, updated_at, workspace_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (project_id, owner_id, title, recipe_json, now, now, workspace_id),
            )
        self._conn.commit()
        return project_id

    def get_recipe(self, project_id: str, owner_id: str) -> Recipe | None:
        row = self._conn.execute(
            "SELECT recipe_json FROM projects WHERE id = ? AND owner_id = ?",
            (project_id, owner_id),
        ).fetchone()
        if row is None:
            return None  # not found OR owned by someone else — same response, per isolation boundary
        return _recipe_from_dict(json.loads(row[0]))

    def list_projects(self, owner_id: str, workspace_id: str | None = None) -> list[ProjectSummary]:
        if workspace_id is not None:
            rows = self._conn.execute(
                "SELECT id, owner_id, title, created_at, updated_at, workspace_id FROM projects "
                "WHERE owner_id = ? AND workspace_id = ? ORDER BY updated_at DESC",
                (owner_id, workspace_id),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id, owner_id, title, created_at, updated_at, workspace_id FROM projects "
                "WHERE owner_id = ? ORDER BY updated_at DESC",
                (owner_id,),
            ).fetchall()
        return [
            ProjectSummary(project_id=r[0], owner_id=r[1], title=r[2], created_at=r[3], updated_at=r[4], workspace_id=r[5])
            for r in rows
        ]

    def delete_recipe(self, project_id: str, owner_id: str) -> bool:
        cur = self._conn.execute(
            "DELETE FROM projects WHERE id = ? AND owner_id = ?", (project_id, owner_id)
        )
        self._conn.commit()
        return cur.rowcount > 0

    def unassign_workspace(self, workspace_id: str, owner_id: str) -> None:
        self._conn.execute(
            "UPDATE projects SET workspace_id = NULL WHERE workspace_id = ? AND owner_id = ?",
            (workspace_id, owner_id),
        )
        self._conn.commit()


def _recipe_to_dict(recipe: Recipe) -> dict:
    d = dataclasses.asdict(recipe)
    return d


def _recipe_from_dict(d: dict) -> Recipe:
    outline_d = d["outline"]
    slides = [
        Slide(
            order=s["order"], title=s["title"],
            content_blocks=[
                ContentBlock(type=BlockType(b["type"]), text=b["text"], media_ref=b.get("media_ref"))
                for b in s["content_blocks"]
            ],
            # ADR-038 fix: these two fields were silently dropped on
            # every load — a saved project's AI-planned layout_type
            # (statistics/comparison/process) and image_query both
            # reverted to their dataclass defaults (bullet_list, None)
            # the moment it was fetched back from storage, discarding
            # real generation work on every single re-export. Found
            # while building slide-level editing, which loads a Recipe
            # from storage, edits it, and needs the untouched slides to
            # stay exactly as they were generated — this bug would have
            # silently broken every "edit slide 3" request by reverting
            # slides 1, 2, 4, 5... to plain bullet lists with no images.
            layout_type=s.get("layout_type", "bullet_list"),
            image_query=s.get("image_query"),
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
