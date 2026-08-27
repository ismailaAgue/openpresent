"""
Export Port — Technical Blueprint Section 3.5.

Responsibility: render a finished Recipe into a downloadable file format.
Each format is an independent adapter; a broken/slow adapter for one
format never affects the others (Constitution Principle 16 / ADR-011).
"""

from typing import Protocol
from backend.models.recipe import Recipe


class UnsupportedFormatError(Exception):
    pass


class ExportPort(Protocol):
    def format_id(self) -> str:
        """e.g. 'pptx', 'pdf', 'docx'"""
        ...

    def export(self, recipe: Recipe) -> bytes:
        """Render the recipe into this adapter's format, returned as bytes."""
        ...
