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


class StoragePort(Protocol):
    def save_recipe(self, owner_id: str, recipe: Recipe, title: str) -> str:
        """Persist a recipe as a project (or new version). Returns project_id."""
        ...

    def get_recipe(self, project_id: str, owner_id: str) -> Recipe | None:
        """Fetch a recipe. Must return None (not raise) if not found OR
        if owner_id doesn't match — this is the per-owner data isolation
        guarantee enforced at the port level (Blueprint Section 11)."""
        ...

    def list_projects(self, owner_id: str) -> list[ProjectSummary]:
        ...

    def delete_recipe(self, project_id: str, owner_id: str) -> bool:
        ...
