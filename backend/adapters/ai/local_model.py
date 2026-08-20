"""
LocalModelAdapter — Technical Blueprint Section 10, ADR-008.

Talks to a local, self-hosted inference engine over its HTTP API
(Ollama-compatible by default: POST /api/generate). This is an
adapter choice, not an architectural commitment (per architect
review amendment #2) — any Ollama-equivalent exposing a similar
HTTP interface can be swapped in via configuration.

Capacity check pattern (Constitution Principle 3 / ADR-008): every
method degrades to the input unmodified if the model is unreachable
or errors — this adapter NEVER raises out to callers for availability
reasons. Errors are caught and treated as "unavailable," so the
AI-optional guarantee holds even when this adapter is misconfigured
or the model server is down.
"""

import json
from typing import Any
from backend.ports.ai import AIPort
from backend.ports.ai_pipeline import AIPipelinePort
from backend.models.recipe import Outline, Slide, ContentBlock, BlockType, StructureSource
from backend.adapters.ai.json_pipeline_base import (
    _JSONPipelineMixin, _TextEnhancementMixin, build_structure_prompt, parse_outline_response,
)
from backend.monitoring.sentry_setup import capture_exception

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:3b"
HEALTH_CHECK_TIMEOUT = 1.5
REQUEST_TIMEOUT = 30


class LocalModelAdapter(_JSONPipelineMixin, _TextEnhancementMixin, AIPort, AIPipelinePort):
    def __init__(self, base_url: str = DEFAULT_BASE_URL, model: str = DEFAULT_MODEL,
                 http_client: Any = None):
        self.base_url = base_url.rstrip("/")
        self.model = model
        # Injectable for tests — avoids needing a real model server to
        # verify this adapter's request/response logic (see
        # tests/contract/test_ai_port.py).
        self._http = http_client or _RequestsHttpClient()

    def is_available(self) -> bool:
        try:
            resp = self._http.get(f"{self.base_url}/api/tags", timeout=HEALTH_CHECK_TIMEOUT)
            return resp.get("status_code", 500) == 200
        except Exception:
            return False

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
                                        "provider": "LocalModelAdapter"})
            return outline  # never raise — degrade to the rule-based baseline

    def rewrite(self, text: str, instructions: str = "") -> str:
        if not self.is_available():
            return text
        try:
            return self._rewrite_raising(text, instructions)
        except Exception as e:
            capture_exception(e, tags={"stage": "ai_port", "method": "rewrite",
                                        "provider": "LocalModelAdapter"})
            return text

    def translate(self, text: str, target_language: str) -> str:
        if not self.is_available():
            return text
        try:
            return self._translate_raising(text, target_language)
        except Exception as e:
            capture_exception(e, tags={"stage": "ai_port", "method": "translate",
                                        "provider": "LocalModelAdapter"})
            return text

    def summarize(self, text: str, max_length: int | None = None) -> str:
        if not self.is_available():
            return text[:max_length] if max_length else text
        try:
            return self._summarize_raising(text, max_length)
        except Exception as e:
            capture_exception(e, tags={"stage": "ai_port", "method": "summarize",
                                        "provider": "LocalModelAdapter"})
            return text[:max_length] if max_length else text

    def suggest(self, context: str) -> list[str]:
        if not self.is_available():
            return []
        try:
            return self._suggest_raising(context)
        except Exception as e:
            capture_exception(e, tags={"stage": "ai_port", "method": "suggest",
                                        "provider": "LocalModelAdapter"})
            return []

    # -- AIPipelinePort (ADR-028/031: local models can also serve
    # topic-first generation — "local models preferred when available"
    # in the provider priority list). All five AIPipelinePort stage
    # methods come from _JSONPipelineMixin; only _call_model() needs
    # implementing here. ------------------------------------------------

    def _call_model(self, prompt: str, max_tokens: int = 4096, timeout: float | None = None) -> str:
        if not self.is_available():
            raise RuntimeError("local model server unavailable")
        return self._generate(prompt, max_tokens=max_tokens, timeout=timeout, json_mode=True)

    # -- AIPort (existing, document-upload enhancement) -------------------
    # Public methods are thin, safe wrappers around _TextEnhancementMixin's
    # _*_raising() methods — see gemini_adapter.py's comment for why
    # (ADR-033: this is what makes composite cascading actually work).

    def _call_text(self, prompt: str, json_mode: bool = False) -> str:
        if not self.is_available():
            raise RuntimeError("local model server unavailable")
        return self._generate(prompt, json_mode=json_mode)

    # -- internals -----------------------------------------------------

    def _generate(self, prompt: str, max_tokens: int = 2048, timeout: float | None = None,
                   json_mode: bool = False) -> str:
        options = {"num_predict": max_tokens}
        request_body = {"model": self.model, "prompt": prompt, "stream": False, "options": options}
        if json_mode:
            # ADR-034: Ollama's own JSON-mode toggle — same fix as
            # json_pipeline_base.py's _propose_structure_raising now
            # requests everywhere, for consistency across all AI
            # adapters rather than relying purely on prompt wording.
            request_body["format"] = "json"
        resp = self._http.post(
            f"{self.base_url}/api/generate",
            # ADR-030 fix: Ollama's num_predict defaults to a modest
            # value in some builds — set explicitly and scaled by
            # caller (see json_pipeline_base.py's _token_budget()), same
            # fix as the hosted providers, for the same reason (silent
            # truncation on larger decks otherwise).
            json=request_body,
            # ADR-030 fix #2: read timeout scaled the same way as
            # max_tokens (_read_timeout()) — see the hosted provider
            # adapters' comments for the production bug this fixes.
            timeout=timeout if timeout is not None else REQUEST_TIMEOUT,
        )
        if resp.get("status_code", 500) != 200:
            raise RuntimeError(f"Model server returned {resp.get('status_code')}")
        return resp.get("json", {}).get("response", "")


class _RequestsHttpClient:
    """Thin wrapper so the adapter doesn't hard-depend on `requests`
    being imported at module load time in environments without it."""

    def get(self, url: str, timeout: float) -> dict:
        import urllib.request
        from backend.adapters.http_headers import with_user_agent
        req = urllib.request.Request(url, method="GET", headers=with_user_agent())
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {"status_code": resp.status, "json": json.loads(resp.read() or b"{}")}

    def post(self, url: str, json: dict, timeout: float) -> dict:
        import urllib.request
        import json as json_mod
        from backend.adapters.http_headers import with_user_agent
        data = json_mod.dumps(json).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST",
                                      headers=with_user_agent({"Content-Type": "application/json"}))
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {"status_code": resp.status, "json": json_mod.loads(resp.read() or b"{}")}
