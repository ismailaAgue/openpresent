"""
Media Port — Phase 3.5 Tier 2 (ADR-025).

Corresponds to the "external stock media" half of the Media Port
described in the Technical Blueprint Section 3.7 (the other half —
user-uploaded image compression — remains unimplemented, out of
scope for this pass). Images are never permanently stored (Blueprint
Section 3.7 / 9's "no large media database" principle) — fetched
fresh at export time, same "generate only when needed" discipline
already applied to the rest of the pipeline.

Same optional-capability discipline as the AI Port: a NullAdapter is
the always-available, zero-cost default; every method must degrade
gracefully (return None) rather than raise when unavailable.
"""

from typing import Protocol


class MediaPort(Protocol):
    def is_available(self) -> bool:
        """Capacity/configuration check. Callers should check this
        before calling search_image, same pattern as AIPort."""
        ...

    def search_image(self, query: str) -> bytes | None:
        """Returns image bytes for the given search query, or None if
        unavailable, misconfigured, or the request failed for any
        reason. Must never raise — a failed image fetch degrades to
        'no image on this slide,' never a broken presentation."""
        ...
