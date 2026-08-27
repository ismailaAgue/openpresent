"""
Workspace Port — ADR-044 (v3 Phase 4, "Project Workspace").

Responsibility: named folders a user groups projects into. A
Workspace is deliberately a thin, separate concept from a Project
(StoragePort already owns projects) — this port only owns the
workspace's own identity (id/name/owner/timestamps), never project
data itself. Cross-cutting operations that touch both (e.g. "what
happens to a workspace's projects when the workspace is deleted")
are coordinated by the caller (an engine or the API layer), not
folded into either port — same separation this codebase already
uses between QueuePort and the generation engines.

Deletion semantics, stated here since it's the one subtle design
choice: deleting a workspace never deletes its projects. A project's
real content (the actual generated Recipe, the whole point of this
product) must never be silently destroyed as a side effect of
deleting an organizational folder — the "recipe, not files" principle
extended to folders. Projects in a deleted workspace become
unassigned (workspace_id reverts to None) rather than disappearing.
"""

from typing import Protocol
from dataclasses import dataclass


@dataclass
class WorkspaceSummary:
    workspace_id: str
    owner_id: str
    name: str
    created_at: float
    updated_at: float


class WorkspacePort(Protocol):
    def create_workspace(self, owner_id: str, name: str) -> str:
        """Returns the new workspace_id."""
        ...

    def get_workspace(self, workspace_id: str, owner_id: str) -> WorkspaceSummary | None:
        """Must return None (not raise) if not found OR owned by
        someone else — same per-owner isolation guarantee StoragePort
        already enforces at the port level."""
        ...

    def list_workspaces(self, owner_id: str) -> list[WorkspaceSummary]:
        ...

    def rename_workspace(self, workspace_id: str, owner_id: str, name: str) -> bool:
        """Returns False (not raise) if not found/not owned."""
        ...

    def delete_workspace(self, workspace_id: str, owner_id: str) -> bool:
        """Deletes the workspace record itself only — never touches
        project data. See module docstring for why. Returns False
        (not raise) if not found/not owned."""
        ...
