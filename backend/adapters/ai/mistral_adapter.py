"""
MistralAdapter — ADR-075 (more free AI providers, to reduce how often
every configured provider's free-tier capacity is exhausted at once —
see ARCHITECTURE_DECISIONS.md for the "AI shortage" problem this and
its sibling adapters exist to mitigate).

Mistral's Chat Completions API is OpenAI-compatible in request/response
shape (confirmed via Mistral's own migration-guide docs: "changing
only the base URL and model name" is the entire migration from OpenAI
client code). base_url already includes /v1 — same convention as
Groq's and OpenRouter's base_url constants in this codebase, so
_OpenAICompatibleBase._chat()'s f"{base_url}/chat/completions" URL
construction needs no special-casing here.

Free tier, verified via live search, not assumed: Mistral's own
"Experiment" plan on La Plateforme — no credit card, rate-limited
(roughly 1 request/second, ~1B tokens/month cap), explicitly for
evaluation/prototyping rather than production, which is exactly the
kind of workload a single OpenPresent generation is. Model
configurable via OPENPRESENT_MISTRAL_MODEL; DEFAULT_MODEL is Mistral's
own "small" tier, the cheap-but-capable default this codebase prefers
across every provider (see groq_adapter.py's DEFAULT_MODEL comment for
the same reasoning).
"""

from backend.adapters.ai.openai_compatible_base import _OpenAICompatibleBase
import os

DEFAULT_MODEL = "mistral-small-latest"


class MistralAdapter(_OpenAICompatibleBase):
    base_url = "https://api.mistral.ai/v1"
    provider_label = "Mistral"

    def __init__(self, api_key: str, model: str | None = None, http_post=None):
        super().__init__(
            api_key=api_key,
            model=model or os.environ.get("OPENPRESENT_MISTRAL_MODEL", DEFAULT_MODEL),
            http_post=http_post,
        )
