"""
Storage Port (recipe persistence half) — Technical Blueprint Section 3.6 / 4.

Persists Recipes as Projects owned by a user — the "recipe, not files"
principle (Constitution Principle 4) made concrete: this port never
stores the generated PPTX/PDF bytes, only the structured Recipe.
"""

from typing import Protocol
from dataclasses import dataclass
from backend.models.recipe import Recipe


@dataclass
class ProjectSummary:
    project_id: str
    owner_id: str
    title: str
    created_at: float
    updated_at: float
    workspace_id: str | None = None  # ADR-044 — None means "ungrouped", not an error


class StoragePort(Protocol):
    def save_recipe(self, owner_id: str, recipe: Recipe, title: str, workspace_id: str | None = None) -> str:
        """Persist a recipe as a project (or new version). Returns
        project_id. workspace_id is optional (ADR-044) — omitting it
        (or passing None) saves an ungrouped project, exactly today's
        behavior; passing a workspace_id assigns it at save time."""
        ...

    def get_recipe(self, project_id: str, owner_id: str) -> Recipe | None:
        """Fetch a recipe. Must return None (not raise) if not found OR
        if owner_id doesn't match — this is the per-owner data isolation
        guarantee enforced at the port level (Blueprint Section 11)."""
        ...

    def list_projects(self, owner_id: str, workspace_id: str | None = None) -> list[ProjectSummary]:
        """workspace_id=None (default) returns every project for this
        owner regardless of workspace assignment — unchanged pre-ADR-044
        behavior. Pass a specific workspace_id to filter to just that
        workspace's projects."""
        ...

    def delete_recipe(self, project_id: str, owner_id: str) -> bool:
        ...

    def unassign_workspace(self, workspace_id: str, owner_id: str) -> None:
        """ADR-044 — sets workspace_id back to None on every project
        currently in this workspace, for this owner. Called when a
        workspace is deleted (see ports/workspace.py's module docstring
        for why deleting a workspace must never delete its projects).
        No-op, not an error, if the workspace has no projects."""
        ...
