"""
Brand Profile Port — ADR-045 (v3 Phase 5, "Brand Memory").

Responsibility: one brand profile per workspace (a 1:1 relationship,
not a separate id/table of many-to-many links — the vision doc's
framing is "every workspace has a brand profile," not "workspaces
choose from a library of brand profiles"). Keyed directly by
workspace_id rather than its own generated id, which is what makes
that 1:1 relationship structurally enforced rather than just a
convention callers have to remember to follow.

Deliberately just descriptive fields consumed by the AI pipeline's
prompts (see AIPipelinePort's generate_strategy and json_pipeline_
base.py's _build_strategy_prompt) — colors/tone/audience/visual style
as free text the model reads, not a structured design-token system
threaded into the deterministic theme/layout renderer. That's a real,
stated scope limit (see ADR-045's full entry in ARCHITECTURE_
DECISIONS.md), not an oversight: mapping freeform brand color
descriptions onto the renderer's actual fixed theme palette is a
separate, harder problem deserving its own pass once there's real
usage data on what people actually type into these fields.
"""

from typing import Protocol
from dataclasses import dataclass


@dataclass
class BrandProfile:
    workspace_id: str
    owner_id: str
    name: str = ""              # e.g. "Acme Corp" — optional, purely descriptive
    colors: str = ""            # free text, e.g. "Blue and purple, modern"
    tone: str = ""              # e.g. "Professional but approachable"
    audience: str = ""          # e.g. "Enterprise investors"
    visual_style: str = ""      # e.g. "Minimal and clean"
    created_at: float = 0.0
    updated_at: float = 0.0

    def is_empty(self) -> bool:
        """True if every actual field is blank — used to treat a
        technically-present-but-all-empty profile the same as no
        profile at all, so an empty PUT doesn't silently start
        injecting a useless empty block into every prompt."""
        return not any([self.name, self.colors, self.tone, self.audience, self.visual_style])


class BrandProfilePort(Protocol):
    def set_brand_profile(self, workspace_id: str, owner_id: str, name: str = "", colors: str = "",
                           tone: str = "", audience: str = "", visual_style: str = "") -> BrandProfile:
        """Upsert — creates on first call, overwrites (whole-record
        replace, not a partial merge) on subsequent calls for the same
        workspace_id. Returns the saved profile."""
        ...

    def get_brand_profile(self, workspace_id: str, owner_id: str) -> BrandProfile | None:
        """Returns None (not raise) if no profile has been set yet, OR
        if workspace_id/owner_id don't match — same per-owner isolation
        guarantee every other port here enforces."""
        ...

    def delete_brand_profile(self, workspace_id: str, owner_id: str) -> bool:
        """Returns False (not raise) if there was nothing to delete."""
        ...
