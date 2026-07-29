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


@dataclass
class Outline:
    structure_source: StructureSource
    slides: list[Slide] = field(default_factory=list)


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
