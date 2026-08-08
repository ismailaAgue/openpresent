"""
Recipe data model — Technical Blueprint Section 5.

This is the canonical, persistent representation of a project. Generated
files (PPTX/PDF/DOCX) are disposable artifacts derived from a Recipe;
the Recipe itself is what gets stored (Constitution Principle 4).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


RECIPE_VERSION = "1.0"


class StructureSource(str, Enum):
    RULE_BASED = "rule-based"
    AI_ENHANCED = "ai-enhanced"
    # AI-first pivot (ADR-028): a topic-based outline generated directly
    # by the AI pipeline (no source document to enhance) rather than a
    # rule-based baseline that AI merely touched up.
    AI_GENERATED = "ai-generated"
    # The topic-mode fallback when no AI pipeline adapter is available —
    # distinct from RULE_BASED (document-derived) so analytics can tell
    # the two "no AI" paths apart.
    DETERMINISTIC_TOPIC = "deterministic-topic"


class BlockType(str, Enum):
    BULLET = "bullet"
    NOTE = "note"
    MEDIA = "media"
    TITLE_TEXT = "title_text"


@dataclass
class ContentBlock:
    type: BlockType
    text: str = ""
    media_ref: str | None = None


@dataclass
class Slide:
    order: int
    title: str
    content_blocks: list[ContentBlock] = field(default_factory=list)
    layout_type: str = "bullet_list"  # Phase 3.5 Step 4: set by Design Engine, read by Export
    image_query: str | None = None  # Phase 3.5 Tier 2 (ADR-025): optional image search hint


@dataclass
class Outline:
    structure_source: StructureSource
    slides: list[Slide] = field(default_factory=list)
    document_type: str = "general"  # Phase 3.5 Step 2: which recipe was applied


@dataclass
class Theme:
    layout_template_id: str = "default"
    color_set_id: str = "default"
    font_set_id: str = "default"


@dataclass
class Recipe:
    """The full, regenerable representation of one presentation version."""
    recipe_version: str
    project_id: str
    source_text: str
    audience_type: str
    language: str
    outline: Outline
    theme: Theme

    @staticmethod
    def new(project_id: str, source_text: str, outline: Outline,
            theme: Theme | None = None, audience_type: str = "student_school",
            language: str = "en") -> "Recipe":
        return Recipe(
            recipe_version=RECIPE_VERSION,
            project_id=project_id,
            source_text=source_text,
            audience_type=audience_type,
            language=language,
            outline=outline,
            theme=theme or Theme(),
        )
