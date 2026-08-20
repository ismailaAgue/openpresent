"""
GroqAdapter — ADR-030 (spec: "other free providers as fallbacks —
should not be hardcoded"). Groq's OpenAI-compatible API, free tier,
known for very fast inference. Model configurable via
OPENPRESENT_GROQ_MODEL (default: a small, fast, currently-free Groq
model — verify against Groq's current free-tier model list at
deployment time, since these change; that's exactly why it's a config
value, not a hardcoded constant).
"""

from backend.adapters.ai.openai_compatible_base import _OpenAICompatibleBase
import os

DEFAULT_MODEL = "llama-3.1-8b-instant"


class GroqAdapter(_OpenAICompatibleBase):
    base_url = "https://api.groq.com/openai/v1"
    provider_label = "Groq"

    def __init__(self, api_key: str, model: str | None = None, http_post=None):
        super().__init__(
            api_key=api_key,
            model=model or os.environ.get("OPENPRESENT_GROQ_MODEL", DEFAULT_MODEL),
            http_post=http_post,
        )
