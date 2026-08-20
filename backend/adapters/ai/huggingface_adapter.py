"""
HuggingFaceAdapter — ADR-030. Hugging Face's Inference Providers
router, which exposes an OpenAI-compatible chat/completions endpoint
across many hosted models (some with free-tier quota) — same shape as
Groq/OpenRouter, so it reuses _OpenAICompatibleBase directly. Model
configurable via OPENPRESENT_HUGGINGFACE_MODEL; verify current free
availability at huggingface.co/docs/inference-providers before relying
on the default in production, same caveat as the other two.
"""

from backend.adapters.ai.openai_compatible_base import _OpenAICompatibleBase
import os

DEFAULT_MODEL = "meta-llama/Llama-3.1-8B-Instruct"


class HuggingFaceAdapter(_OpenAICompatibleBase):
    base_url = "https://router.huggingface.co/v1"
    provider_label = "HuggingFace"

    def __init__(self, api_key: str, model: str | None = None, http_post=None):
        super().__init__(
            api_key=api_key,
            model=model or os.environ.get("OPENPRESENT_HUGGINGFACE_MODEL", DEFAULT_MODEL),
            http_post=http_post,
        )
