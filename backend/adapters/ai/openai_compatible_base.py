"""
_OpenAICompatibleBase — ADR-030 (additional AI providers, spec Section 6).

Groq and OpenRouter both expose an OpenAI-compatible `/chat/completions`
endpoint, so one shared base class covers both — only base_url, model,
and a couple of headers differ per subclass. This is the concrete
"changing inference backends should not require application rewrites"
guarantee: a third OpenAI-compatible provider later is a ~15-line
subclass, not new pipeline logic.
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

REQUEST_TIMEOUT = 45


class _OpenAICompatibleBase(_JSONPipelineMixin, _TextEnhancementMixin, AIPort, AIPipelinePort):
    base_url: str = ""       # set by subclass
    provider_label: str = ""  # for error messages only

    def __init__(self, api_key: str, model: str, http_post=None):
        self.api_key = api_key
        self.model = model
        self._post = http_post or _post_json

    def is_available(self) -> bool:
        return bool(self.api_key)

    # -- AIPipelinePort -----------------------------------------------

    def _call_model(self, prompt: str, max_tokens: int = 4096, timeout: float | None = None) -> str:
        return self._chat(prompt, json_mode=True, max_tokens=max_tokens, timeout=timeout)

    # -- AIPort (document-upload enhancement) --------------------------

    def propose_structure(self, outline: Outline, source_text: str,
                           target_slide_count: int | None = None) -> Outline:
        if not self.is_available():
            return outline
        try:
            return self._propose_structure_raising(outline, source_text, target_slide_count)
        except Exception as e:
            # ADR-033 fix: previously swallowed with zero visibility —
            # same invisible-failure bug class as ADR-031's Bug 1.
            capture_exception(e, tags={"stage": "ai_port", "method": "propose_structure",
                                        "provider": self.provider_label})
            return outline

    def rewrite(self, text: str, instructions: str = "") -> str:
        if not self.is_available():
            return text
        try:
            return self._rewrite_raising(text, instructions)
        except Exception as e:
            capture_exception(e, tags={"stage": "ai_port", "method": "rewrite",
                                        "provider": self.provider_label})
            return text

    def translate(self, text: str, target_language: str) -> str:
        if not self.is_available():
            return text
        try:
            return self._translate_raising(text, target_language)
        except Exception as e:
            capture_exception(e, tags={"stage": "ai_port", "method": "translate",
                                        "provider": self.provider_label})
            return text

    def summarize(self, text: str, max_length: int | None = None) -> str:
        if not self.is_available():
            return text[:max_length] if max_length else text
        try:
            return self._summarize_raising(text, max_length)
        except Exception as e:
            capture_exception(e, tags={"stage": "ai_port", "method": "summarize",
                                        "provider": self.provider_label})
            return text[:max_length] if max_length else text

    def suggest(self, context: str) -> list[str]:
        if not self.is_available():
            return []
        try:
            return self._suggest_raising(context)
        except Exception as e:
            capture_exception(e, tags={"stage": "ai_port", "method": "suggest",
                                        "provider": self.provider_label})
            return []

    # -- internals -------------------------------------------------------

    def _call_text(self, prompt: str, json_mode: bool = False) -> str:
        return self._chat(prompt, json_mode=json_mode)

    def _chat(self, prompt: str, json_mode: bool = False, max_tokens: int = 2048,
              timeout: float | None = None) -> str:
        body: dict = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            # ADR-030 fix: previously unset, silently inheriting each
            # provider's own default max_tokens — some free-tier
            # defaults are modest enough to truncate a multi-slide JSON
            # response, causing a parse failure and a full fallback to
            # the deterministic template as slide count grew (same bug
            # class as the Gemini/local-model fix — see those adapters'
            # comments). Now always explicit, scaled by caller.
            "max_tokens": max_tokens,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        # ADR-030 fix #2: read timeout scaled the same way as
        # max_tokens (json_pipeline_base.py's _read_timeout()) — a
        # bigger token budget takes proportionally longer to generate;
        # a fixed timeout tuned for a short response was cutting off a
        # still-in-progress larger one (the actual bug this fixes was
        # caught live: TimeoutError on a 10-slide content-generation
        # call against the old fixed 45s timeout).
        effective_timeout = timeout if timeout is not None else REQUEST_TIMEOUT
        response = self._post(f"{self.base_url}/chat/completions", self.api_key, body, effective_timeout)
        choices = response.get("choices") or []
        if not choices:
            raise RuntimeError(f"{self.provider_label} returned no choices")
        finish_reason = choices[0].get("finish_reason")
        content = ((choices[0].get("message") or {}).get("content") or "").strip()
        if not content:
            raise RuntimeError(f"{self.provider_label} returned an empty response "
                                f"(finish_reason={finish_reason})")
        if finish_reason == "length":
            # Caught explicitly rather than left to surface as a generic
            # JSON parse error downstream — much faster to diagnose from
            # logs if this budget is ever still too small.
            raise RuntimeError(f"{self.provider_label} response was truncated at "
                                f"max_tokens={max_tokens} (finish_reason=length) — "
                                f"response may be incomplete JSON")
        return content


def _post_json(url: str, api_key: str, body: dict, timeout: float) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        # ADR-034 fix: this is the concrete, confirmed fix for a real
        # production failure — Groq's Cloudflare protection was
        # returning 403/error-1010 for every request from this
        # adapter, which is Cloudflare's Bot Management blocking
        # urllib's default "Python-urllib/x.y" User-Agent outright,
        # before the request ever reached Groq's own API. Confirmed
        # against Groq's own community forum, which documents this
        # exact error and this exact fix.
        headers=with_user_agent({"Content-Type": "application/json",
                                  "Authorization": f"Bearer {api_key}"}),
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"API error {e.code}: {detail}") from e
