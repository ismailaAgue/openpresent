"""
Structure Engine Port — Technical Blueprint Section 3.2.

Responsibility: convert extracted text into a slide-by-slide Outline.
The default adapter is rule-based and must be genuinely good on its own
(Constitution Principle 15) — AI only ever enhances this, never replaces
the requirement that this path works alone.
"""

from typing import Protocol
from backend.models.recipe import Outline


class StructurePort(Protocol):
    def build_outline(self, source_text: str, audience_type: str, export_format: str = "pptx") -> Outline:
        """
        Build a slide-by-slide outline from source text.
        Must never raise for any non-empty text input — worst case,
        return a minimal single-slide outline. Empty/whitespace-only
        input should raise ValueError.

        export_format (ADR-054): defaults to "pptx" so every existing
        caller keeps its exact prior behavior unless updated. When
        "document_docx", plain prose sections (no bullet markers in
        the source) are kept as one connected paragraph per section
        instead of being split into one-bullet-per-sentence fragments
        — sentence-splitting is correct when the eventual output is a
        slide deck (each sentence really should be its own bullet) but
        actively wrong when it's a Word document (it shatters real
        prose into a list that was never meant to be one). Content
        that genuinely IS a list in the source (explicit bullet
        markers) still splits per-item regardless of export_format —
        a real list stays a real list in a document too.
        """
        ...
