"""
OpenRouterAdapter — ADR-030, model default revised ADR-034.

OpenRouter's OpenAI-compatible API. Free-tier model availability
churns fast and unpredictably in practice — real-world monitoring in
mid-2026 showed entire free model families (e.g. Meta's whole free
Llama tier) delisted within a single week, with individual :free
slugs commonly surviving only days to weeks before being pulled or
moved to paid-only. A production failure was traced to exactly this:
the originally-hardcoded meta-llama/llama-3.1-8b-instruct:free slug
returned "unavailable for free, use the paid version instead."

DEFAULT_MODEL is therefore "openrouter/free" — OpenRouter's own
auto-router alias (not a specific model), which is purpose-built for
this exact problem: it dynamically selects from whichever free models
are currently available and matches the request's needs, so this
adapter keeps working across individual free-model rotations without
needing a code or config change every time the underlying roster
shifts. Still overridable via OPENPRESENT_OPENROUTER_MODEL if a
specific model is ever preferred (e.g. for consistent output style),
with the explicit tradeoff that a hardcoded specific slug will need
periodic manual updates as this codebase's history now demonstrates.
"""

from backend.adapters.ai.openai_compatible_base import _OpenAICompatibleBase
import os

DEFAULT_MODEL = "openrouter/free"


class OpenRouterAdapter(_OpenAICompatibleBase):
    base_url = "https://openrouter.ai/api/v1"
    provider_label = "OpenRouter"

    def __init__(self, api_key: str, model: str | None = None, http_post=None):
        super().__init__(
            api_key=api_key,
            model=model or os.environ.get("OPENPRESENT_OPENROUTER_MODEL", DEFAULT_MODEL),
            http_post=http_post,
        )
