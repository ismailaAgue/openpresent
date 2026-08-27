"""
Slide-level editing / partial regeneration — ADR-038.

Two distinct operations on an already-saved project:

  - edit_slide_manually: the user directly supplies new title/bullets/
    notes for one slide. No AI involved — a pure data update. Always
    available, regardless of whether any AI provider is configured.

  - regenerate_slide_ai: the user asks AI to rewrite one slide (with
    optional freeform instructions, e.g. "make this more concise" or
    "focus on economic impact instead"), leaving every OTHER slide in
    the deck completely untouched. This is the actual "partial
    regeneration" capability — re-running the whole 5-stage pipeline
    for a one-slide tweak would be wasteful (cost, latency) and risks
    silently changing slides the user was happy with.

Why this doesn't need the original PresentationStrategy to be
persisted: the Recipe already carries everything a regeneration
genuinely needs — source_text (which is "Topic: X" for topic-mode
decks, or an excerpt of the original document for upload-mode decks),
audience_type, language, and every slide's own title for narrative-
consistency context. The narrative_style/title_angle/key_themes that
generate_strategy() originally produced are useful DURING full
generation but aren't required to sanely regenerate one already-
written slide in the context of its siblings.

Known scope boundary, not a bug: regeneration only touches a slide's
title/bullets/notes — layout_type and image_query are left exactly as
they were. If a regenerated slide's content shifts enough that its
layout no longer fits (e.g. was "process", new content is stats-heavy),
that's not auto-corrected. Re-running AI-driven layout planning on
every edit would mean an extra AI call plus a potential new image
fetch on every single slide tweak — judged not worth the cost for an
edit action a user will typically use several times while iterating.
"""

from backend.adapters import registry
from backend.models.recipe import Recipe, BlockType, ContentBlock
from backend.ports.ai_pipeline import SlideRegenerationContext
from backend.monitoring.sentry_setup import capture_exception


class ProjectNotFoundError(Exception):
    pass


class SlideNotFoundError(Exception):
    pass


class AIUnavailableError(Exception):
    """Raised only by regenerate_slide_ai — there is no honest
    deterministic substitute for 'AI, rewrite this slide' the way
    there is for whole-deck generation (which has the topic-template
    fallback). Editing manually is always the alternative."""
    pass


def _load_owned_recipe(project_id: str, owner_id: str) -> Recipe:
    storage = registry.get_storage_adapter()
    recipe = storage.get_recipe(project_id, owner_id)
    if recipe is None:
        raise ProjectNotFoundError(project_id)
    return recipe


def _find_slide(recipe: Recipe, slide_order: int):
    for slide in recipe.outline.slides:
        if slide.order == slide_order:
            return slide
    raise SlideNotFoundError(slide_order)


def _save(owner_id: str, recipe: Recipe) -> str:
    storage = registry.get_storage_adapter()
    title = recipe.outline.slides[0].title if recipe.outline.slides else "Untitled"
    return storage.save_recipe(owner_id, recipe, title)


def edit_slide_manually(project_id: str, slide_order: int, owner_id: str,
                         title: str | None = None, bullets: list[str] | None = None,
                         notes: str | None = None) -> Recipe:
    """Direct, no-AI edit — every field is optional, only supplied
    fields are changed. At least one of title/bullets/notes must be
    given (an edit with nothing to change is a caller bug, not
    something to silently accept)."""
    if title is None and bullets is None and notes is None:
        raise ValueError("edit_slide_manually requires at least one of title/bullets/notes")

    recipe = _load_owned_recipe(project_id, owner_id)
    slide = _find_slide(recipe, slide_order)

    if title is not None:
        slide.title = title.strip()[:90] or slide.title

    if bullets is not None:
        new_bullet_blocks = [ContentBlock(type=BlockType.BULLET, text=b.strip()[:160])
                              for b in bullets if b.strip()]
        non_bullet_blocks = [b for b in slide.content_blocks if b.type != BlockType.BULLET]
        slide.content_blocks = new_bullet_blocks + non_bullet_blocks

    if notes is not None:
        non_note_blocks = [b for b in slide.content_blocks if b.type != BlockType.NOTE]
        note_text = notes.strip()[:700]
        slide.content_blocks = non_note_blocks + ([ContentBlock(type=BlockType.NOTE, text=note_text)]
                                                    if note_text else [])

    _save(owner_id, recipe)
    return recipe


def regenerate_slide_ai(project_id: str, slide_order: int, owner_id: str,
                         instructions: str | None = None) -> Recipe:
    """AI-assisted regeneration of exactly one slide. Raises
    AIUnavailableError if no AI provider is configured — there is
    deliberately no silent fallback here (see module docstring)."""
    pipeline = registry.get_ai_pipeline_adapter()
    if not pipeline.is_available():
        raise AIUnavailableError(
            "No AI provider is configured — use the manual edit endpoint instead, "
            "or configure an AI provider (GEMINI_API_KEY, GROQ_API_KEY, etc.)."
        )

    recipe = _load_owned_recipe(project_id, owner_id)
    slide = _find_slide(recipe, slide_order)

    context = SlideRegenerationContext(
        topic_or_source_summary=recipe.source_text,
        audience_type=recipe.audience_type,
        language=recipe.language,
        other_slide_titles=[s.title for s in recipe.outline.slides if s.order != slide_order],
        current_title=slide.title,
        current_bullets=[b.text for b in slide.content_blocks if b.type == BlockType.BULLET],
        current_notes=next((b.text for b in slide.content_blocks if b.type == BlockType.NOTE), ""),
        instructions=instructions,
    )

    try:
        new_title, new_bullets, new_notes = pipeline.regenerate_slide(context)
    except Exception as e:
        capture_exception(e, tags={"stage": "slide_regeneration", "project_id": project_id,
                                    "slide_order": str(slide_order)})
        raise AIUnavailableError(f"AI regeneration failed: {e}") from e

    slide.title = new_title
    blocks = [ContentBlock(type=BlockType.BULLET, text=b) for b in new_bullets]
    if new_notes:
        blocks.append(ContentBlock(type=BlockType.NOTE, text=new_notes))
    slide.content_blocks = blocks

    _save(owner_id, recipe)
    return recipe
