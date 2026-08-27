"""
Export bundling — ADR-030.

Packages the primary export (PPTX today; any future ExportPort format
tomorrow) together with the speaker-notes DOCX companion
(backend/adapters/export/docx_notes_adapter.py) into a single .zip —
the concrete answer to "export should be PPT plus speaker notes in a
separate file, docx format." Bundling happens here, once, so both
/generate and /generate/topic (sync and async) get identical behavior
without duplicating zip logic in the API layer.
"""

import io
import zipfile
from backend.models.recipe import Recipe
from backend.adapters.export.docx_notes_adapter import SpeakerNotesDocxExportAdapter

_NOTES_EXPORTER = SpeakerNotesDocxExportAdapter()


def build_export_bundle(recipe: Recipe, primary_bytes: bytes, primary_format: str) -> bytes:
    """Returns zip bytes containing presentation.<primary_format> and
    speaker_notes.docx. The notes doc is always regenerated from the
    same Recipe as the primary export — impossible for them to drift
    out of sync with each other."""
    notes_bytes = _NOTES_EXPORTER.export(recipe)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"presentation.{primary_format}", primary_bytes)
        zf.writestr("speaker_notes.docx", notes_bytes)
    return buf.getvalue()
