"""
CohereAdapter — ADR-075.

Cohere's native Chat API has its own request/response shape, but
Cohere also publishes a dedicated OpenAI-Compatibility API at
"https://api.cohere.ai/compatibility/v1" — confirmed via multiple
independent integration guides (Langfuse, Opik, Strands Agents), all
showing the standard OpenAI SDK pointed at that exact base URL with no
translation layer, `response.choices[0].message.content` included.
That's the endpoint this adapter uses, not Cohere's native one — using
the native shape would need real translation logic this shared base
class doesn't do.

Free tier, verified via live search, not assumed: a Trial API key is
issued automatically on signup, no credit card. **Stated limitation:**
smaller than this file's other free-tier adapters — capped at 1,000
API calls/month (not a token cap, a call cap) and 20 requests/minute
for the Chat endpoint specifically. Genuinely useful as one more layer
in the fallback cascade, not a primary workhorse the way Groq's or
Cerebras's more generous daily allowances are. Model configurable via
OPENPRESENT_COHERE_MODEL; DEFAULT_MODEL is Command R — Cohere's
balanced mid-tier model, available on trial keys.
"""

from backend.adapters.ai.openai_compatible_base import _OpenAICompatibleBase
import os

DEFAULT_MODEL = "command-r-08-2024"


class CohereAdapter(_OpenAICompatibleBase):
    base_url = "https://api.cohere.ai/compatibility/v1"
    provider_label = "Cohere"

    def __init__(self, api_key: str, model: str | None = None, http_post=None):
        super().__init__(
            api_key=api_key,
            model=model or os.environ.get("OPENPRESENT_COHERE_MODEL", DEFAULT_MODEL),
            http_post=http_post,
        )
