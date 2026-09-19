"""
CerebrasAdapter — ADR-075.

Cerebras's Chat Completions API is OpenAI-compatible: their own
official docs show the OpenAI Python SDK pointed directly at
"https://api.cerebras.ai/v1" as the standard integration path, no
translation layer needed.

Free tier, verified via live search, not assumed: no credit card,
generous daily token allowance (independently reported around
1,000,000 tokens/day on their fast LPU hardware) — one of the more
generous standing free tiers checked while adding this batch of
providers. **Stated caveat, not hidden:** at least one independent
source (dated April 2026, ahead of others dated June-August 2026
describing a no-card tier) reported Cerebras had at some point required
a card for a trial. Free-tier terms across this whole industry have
proven to change without much notice in 2026 (this file's own sibling
adapters ran into concrete examples: DeepSeek deprecated model names
mid-year, OpenAI's free-tier terms changed twice) — if this adapter
ever reports GROQ_API_KEY-style unavailability unexpectedly, check
Cerebras's current terms before assuming it's a code bug. Model
configurable via OPENPRESENT_CEREBRAS_MODEL; DEFAULT_MODEL is
Cerebras's Llama 3.3 70B — a solid, general-purpose model available on
their free tier as of writing.
"""

from backend.adapters.ai.openai_compatible_base import _OpenAICompatibleBase
import os

DEFAULT_MODEL = "llama-3.3-70b"


class CerebrasAdapter(_OpenAICompatibleBase):
    base_url = "https://api.cerebras.ai/v1"
    provider_label = "Cerebras"

    def __init__(self, api_key: str, model: str | None = None, http_post=None):
        super().__init__(
            api_key=api_key,
            model=model or os.environ.get("OPENPRESENT_CEREBRAS_MODEL", DEFAULT_MODEL),
            http_post=http_post,
        )
