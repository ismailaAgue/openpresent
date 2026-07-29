"""
Generation engine — Technical Blueprint Section 5, "Request Flow."

Orchestrates: Ingestion -> Structure (rule-based) -> AI Port (optional
enhancement) -> Design -> Export.

This is Path A + the optional Path B enhancement step in one function.
Path A alone (AI unavailable) must always produce a usable result —
that's the guarantee this engine exists to enforce structurally.
"""

import uuid
from backend.adapters import registry
from backend.models.recipe import Recipe


def generate_presentation(file_bytes: bytes, filename: str, export_format: str = "pptx",
                           audience_type: str = "student_school", language: str = "en",
                           project_id: str | None = None) -> tuple[Recipe, bytes]:
    project_id = project_id or str(uuid.uuid4())

    ingestion = registry.get_ingestion_adapter(filename)
    source_text = ingestion.extract_text(file_bytes, filename)

    structure = registry.get_structure_adapter()
    outline = structure.build_outline(source_text, audience_type)

    ai = registry.get_ai_adapter()
    if ai.is_available():
        outline = ai.propose_structure(outline, source_text)
    # If AI is unavailable, outline stays exactly as the rule-based
    # engine produced it — no error, no block, no visible difference
    # to the calling code. This is the enforced guarantee, not a hope.

    design = registry.get_design_adapter()
    from backend.models.recipe import Theme
    recipe = design.apply_theme(
        project_id=project_id,
        source_text=source_text,
        outline=outline,
        theme=Theme(),
        audience_type=audience_type,
        language=language,
    )

    exporter = registry.get_export_adapter(export_format)
    file_out = exporter.export(recipe)

    return recipe, file_out
