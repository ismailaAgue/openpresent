"""
GeminiAdapter — ADR-028, default hosted AI provider.

Implements BOTH ports:
- AIPort (backend/ports/ai.py) — the original document-enhancement
  capability (title rewriting, translation, etc. for the upload flow).
- AIPipelinePort (backend/ports/ai_pipeline.py) — the new topic-first
  generation capability.

One adapter, two ports, because it's the same underlying provider —
this is exactly the "provider independence" the spec asks for
(Section 6 / 18): swapping Gemini for another OpenAI-compatible or
Gemini-compatible hosted provider later is a new adapter class plus a
one-line registry change, not a rewrite of engines/ or api/.

Provider priority (per product decision, ADR-028):
  1. Local models (OPENPRESENT_AI_ADAPTER=local_model) — $0, dev/self-host
  2. Gemini API free tier (this adapter) — default hosted provider
  3. Other OpenAI-compatible free providers — future adapters, same shape
  4. Premium providers — only once revenue justifies the cost

Uses the Gemini REST API directly over urllib (stdlib only, matching
LocalModelAdapter's dependency discipline — no new package required
for the MVP). Model name is configurable (OPENPRESENT_GEMINI_MODEL)
so bumping to a newer Gemini model is a config change, never a code
change.

Availability discipline: is_available() only checks that an API key
is configured — it deliberately does NOT make a network call (unlike
LocalModelAdapter's is_available(), which pings a same-host localhost
server that's cheap to reach). A real network round trip to Gemini on
every /health check and every generation attempt would burn free-tier
quota for no benefit; actual reachability failures are caught and
degraded at call time instead, same guarantee, cheaper to check.
"""

import json
import os
import urllib.error
import urllib.request
from backend.ports.ai import AIPort
from backend.ports.ai_pipeline import AIPipelinePort
from backend.adapters.ai.json_pipeline_base import (
    _JSONPipelineMixin, build_structure_prompt, parse_outline_response,
)
from backend.models.recipe import Outline

DEFAULT_MODEL = "gemini-2.0-flash"
API_BASE = "https://generativelanguage.googleapis.com/v1beta"
REQUEST_TIMEOUT = 45


class GeminiAdapter(_JSONPipelineMixin, AIPort, AIPipelinePort):
    def __init__(self, api_key: str, model: str | None = None, http_post=None):
        self.api_key = api_key
        self.model = model or os.environ.get("OPENPRESENT_GEMINI_MODEL", DEFAULT_MODEL)
        # Injectable for tests, same pattern as LocalModelAdapter's http_client.
        self._post = http_post or _post_json

    def is_available(self) -> bool:
        return bool(self.api_key)

    # -- AIPipelinePort (new, topic-first) -------------------------------
    # generate_presentation_outline / review_and_revise come from
    # _JSONPipelineMixin — only _call_model needs implementing here.

    def _call_model(self, prompt: str) -> str:
        return self._generate_text(prompt, json_mode=True)

    # -- AIPort (existing, document-upload enhancement) ------------------

    def propose_structure(self, outline: Outline, source_text: str) -> Outline:
        if not self.is_available():
            return outline
        try:
            prompt = build_structure_prompt(outline, source_text)
            raw = self._generate_text(prompt, json_mode=True)
            return parse_outline_response(raw, fallback=outline)
        except Exception:
            return outline

    def rewrite(self, text: str, instructions: str = "") -> str:
        if not self.is_available():
            return text
        try:
            prompt = f"Rewrite the following text. {instructions}\n\nText: {text}\n\nRewritten:"
            result = self._generate_text(prompt).strip().strip('"').strip("'")
            return result or text
        except Exception:
            return text

    def translate(self, text: str, target_language: str) -> str:
        if not self.is_available():
            return text
        try:
            prompt = f"Translate the following text to {target_language}. Return only the translation.\n\nText: {text}"
            return self._generate_text(prompt).strip() or text
        except Exception:
            return text

    def summarize(self, text: str, max_length: int | None = None) -> str:
        if not self.is_available():
            return text[:max_length] if max_length else text
        try:
            length_hint = f" in under {max_length} characters" if max_length else ""
            prompt = f"Summarize the following text{length_hint}.\n\nText: {text}"
            result = self._generate_text(prompt).strip()
            return result or text
        except Exception:
            return text[:max_length] if max_length else text

    def suggest(self, context: str) -> list[str]:
        if not self.is_available():
            return []
        try:
            prompt = f"Given this context, suggest up to 3 short improvements, one per line:\n\n{context}"
            raw = self._generate_text(prompt)
            return [line.strip("- ").strip() for line in raw.splitlines() if line.strip()][:3]
        except Exception:
            return []

    # -- internals --------------------------------------------------------

    def _generate_text(self, prompt: str, json_mode: bool = False) -> str:
        body: dict = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.7},
        }
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"

        url = f"{API_BASE}/models/{self.model}:generateContent?key={self.api_key}"
        response = self._post(url, body, REQUEST_TIMEOUT)

        candidates = response.get("candidates") or []
        if not candidates:
            block_reason = (response.get("promptFeedback") or {}).get("blockReason")
            raise RuntimeError(f"Gemini returned no candidates (blockReason={block_reason})")

        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts)
        if not text:
            raise RuntimeError("Gemini returned an empty response")
        return text


def _post_json(url: str, body: dict, timeout: float) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST", headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Gemini API error {e.code}: {detail}") from e
