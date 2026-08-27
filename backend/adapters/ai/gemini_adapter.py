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
change — which matters in practice: DEFAULT_MODEL has already needed
updating once (ADR-034) after Google fully shut down the original
gemini-2.0-flash default on June 1, 2026, confirming Google's own
deprecation-cadence warnings that hardcoded model IDs are a real
production liability, not a theoretical one. Re-verify the current
default against ai.google.dev/gemini-api/docs/deprecations
periodically — this codebase has no automated way to detect a
provider's own model retirement in advance.

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
    _JSONPipelineMixin, _TextEnhancementMixin, build_structure_prompt, parse_outline_response,
)
from backend.models.recipe import Outline
from backend.monitoring.sentry_setup import capture_exception
from backend.adapters.http_headers import with_user_agent

DEFAULT_MODEL = "gemini-3.5-flash"
API_BASE = "https://generativelanguage.googleapis.com/v1beta"
REQUEST_TIMEOUT = 45


class GeminiAdapter(_JSONPipelineMixin, _TextEnhancementMixin, AIPort, AIPipelinePort):
    def __init__(self, api_key: str, model: str | None = None, http_post=None):
        self.api_key = api_key
        self.model = model or os.environ.get("OPENPRESENT_GEMINI_MODEL", DEFAULT_MODEL)
        # Injectable for tests, same pattern as LocalModelAdapter's http_client.
        self._post = http_post or _post_json

    def is_available(self) -> bool:
        return bool(self.api_key)

    # -- AIPipelinePort (new, topic-first) -------------------------------
    # generate_strategy / generate_outline_structure / generate_slide_content
    # / plan_layout / review_and_revise all come from _JSONPipelineMixin —
    # only _call_model needs implementing here.

    def _call_model(self, prompt: str, max_tokens: int = 4096, timeout: float | None = None) -> str:
        return self._generate_text(prompt, json_mode=True, max_tokens=max_tokens, timeout=timeout)

    # -- AIPort (existing, document-upload enhancement) ------------------
    # Public methods are thin, safe wrappers around _TextEnhancementMixin's
    # _*_raising() methods — this is what CompositeAIAdapter cascades
    # through directly (ADR-033) when multiple providers are configured;
    # these wrappers exist for correct standalone (single-adapter)
    # behavior, degrading to the original input rather than raising.

    def _call_text(self, prompt: str, json_mode: bool = False) -> str:
        return self._generate_text(prompt, json_mode=json_mode)

    def propose_structure(self, outline: Outline, source_text: str,
                           target_slide_count: int | None = None) -> Outline:
        if not self.is_available():
            return outline
        try:
            return self._propose_structure_raising(outline, source_text, target_slide_count)
        except Exception as e:
            # ADR-033 fix: this used to swallow every failure silently —
            # the document-upload flow's AI enhancement could be failing
            # on every single request with zero visibility anywhere,
            # same invisible-failure bug class as ADR-031's Bug 1, just
            # in AIPort's methods instead of AIPipelinePort's.
            capture_exception(e, tags={"stage": "ai_port", "method": "propose_structure",
                                        "provider": "GeminiAdapter"})
            return outline

    def rewrite(self, text: str, instructions: str = "") -> str:
        if not self.is_available():
            return text
        try:
            return self._rewrite_raising(text, instructions)
        except Exception as e:
            capture_exception(e, tags={"stage": "ai_port", "method": "rewrite",
                                        "provider": "GeminiAdapter"})
            return text

    def translate(self, text: str, target_language: str) -> str:
        if not self.is_available():
            return text
        try:
            return self._translate_raising(text, target_language)
        except Exception as e:
            capture_exception(e, tags={"stage": "ai_port", "method": "translate",
                                        "provider": "GeminiAdapter"})
            return text

    def summarize(self, text: str, max_length: int | None = None) -> str:
        if not self.is_available():
            return text[:max_length] if max_length else text
        try:
            return self._summarize_raising(text, max_length)
        except Exception as e:
            capture_exception(e, tags={"stage": "ai_port", "method": "summarize",
                                        "provider": "GeminiAdapter"})
            return text[:max_length] if max_length else text

    def suggest(self, context: str) -> list[str]:
        if not self.is_available():
            return []
        try:
            return self._suggest_raising(context)
        except Exception as e:
            capture_exception(e, tags={"stage": "ai_port", "method": "suggest",
                                        "provider": "GeminiAdapter"})
            return []

    def answer_question(self, context: str, question: str) -> str:
        if not self.is_available():
            return "AI is not configured for this deployment, so I can't answer questions about this document."
        try:
            return self._answer_question_raising(context, question)
        except Exception as e:
            capture_exception(e, tags={"stage": "ai_port", "method": "answer_question",
                                        "provider": "GeminiAdapter"})
            return "The AI provider couldn't answer that question right now — please try again."

    # -- internals --------------------------------------------------------

    def _generate_text(self, prompt: str, json_mode: bool = False, max_tokens: int = 2048,
                        timeout: float | None = None) -> str:
        body: dict = {
            "contents": [{"parts": [{"text": prompt}]}],
            # ADR-030 fix: maxOutputTokens was previously unset, silently
            # inheriting Gemini's default — fine for small prompts, but it
            # truncated the JSON response (causing a parse failure and a
            # full fallback to the deterministic template) once slide
            # count grew past a handful. Now always explicit, scaled by
            # caller (see json_pipeline_base.py's _token_budget()).
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": max_tokens},
        }
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"

        url = f"{API_BASE}/models/{self.model}:generateContent?key={self.api_key}"
        # ADR-030 fix #2: read timeout scaled the same way as
        # max_tokens (see json_pipeline_base.py's _read_timeout()) — a
        # bigger token budget takes proportionally longer to actually
        # generate; a fixed timeout tuned for a short response was
        # cutting off a still-in-progress larger one.
        response = self._post(url, body, timeout if timeout is not None else REQUEST_TIMEOUT)

        candidates = response.get("candidates") or []
        if not candidates:
            block_reason = (response.get("promptFeedback") or {}).get("blockReason")
            raise RuntimeError(f"Gemini returned no candidates (blockReason={block_reason})")

        finish_reason = candidates[0].get("finishReason")
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts)
        if not text:
            raise RuntimeError(f"Gemini returned an empty response (finishReason={finish_reason})")
        if finish_reason == "MAX_TOKENS":
            # Caught explicitly rather than left to surface as a generic
            # JSON parse error downstream — much faster to diagnose from
            # logs (see monitoring/sentry_setup.py) if this budget is
            # ever still too small for an unusually large request.
            raise RuntimeError(f"Gemini response was truncated at max_tokens={max_tokens} "
                                f"(finishReason=MAX_TOKENS) — response may be incomplete JSON")
        return text


def _post_json(url: str, body: dict, timeout: float) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers=with_user_agent({"Content-Type": "application/json"}),
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Gemini API error {e.code}: {detail}") from e
