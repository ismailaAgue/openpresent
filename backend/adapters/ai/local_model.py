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
    _JSONPipelineMixin, build_structure_prompt, parse_outline_response,
)

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:3b"
HEALTH_CHECK_TIMEOUT = 1.5
REQUEST_TIMEOUT = 30


class LocalModelAdapter(_JSONPipelineMixin, AIPort, AIPipelinePort):
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

    def propose_structure(self, outline: Outline, source_text: str) -> Outline:
        if not self.is_available():
            return outline

        prompt = build_structure_prompt(outline, source_text)
        try:
            raw = self._generate(prompt)
            improved = parse_outline_response(raw, fallback=outline)
            return improved
        except Exception:
            return outline  # never raise — degrade to the rule-based baseline

    def rewrite(self, text: str, instructions: str = "") -> str:
        if not self.is_available():
            return text
        try:
            prompt = f"Rewrite the following text. {instructions}\n\nText: {text}\n\nRewritten:"
            return self._generate(prompt).strip() or text
        except Exception:
            return text

    def translate(self, text: str, target_language: str) -> str:
        if not self.is_available():
            return text
        try:
            prompt = f"Translate the following text to {target_language}. Return only the translation.\n\nText: {text}"
            return self._generate(prompt).strip() or text
        except Exception:
            return text

    def summarize(self, text: str, max_length: int | None = None) -> str:
        if not self.is_available():
            return text[:max_length] if max_length else text
        try:
            length_hint = f" in under {max_length} characters" if max_length else ""
            prompt = f"Summarize the following text{length_hint}.\n\nText: {text}"
            result = self._generate(prompt).strip()
            return result or text
        except Exception:
            return text[:max_length] if max_length else text

    def suggest(self, context: str) -> list[str]:
        if not self.is_available():
            return []
        try:
            prompt = f"Given this context, suggest up to 3 short improvements, one per line:\n\n{context}"
            raw = self._generate(prompt)
            return [line.strip("- ").strip() for line in raw.splitlines() if line.strip()][:3]
        except Exception:
            return []

    # -- AIPipelinePort (ADR-028: local models can also serve topic-first
    # generation — "local models preferred when available" in the
    # provider priority list). generate_presentation_outline() and
    # review_and_revise() come from _JSONPipelineMixin; only
    # _call_model() needs implementing here. -------------------------

    def _call_model(self, prompt: str) -> str:
        if not self.is_available():
            raise RuntimeError("local model server unavailable")
        return self._generate(prompt)

    # -- internals -----------------------------------------------------

    def _generate(self, prompt: str) -> str:
        resp = self._http.post(
            f"{self.base_url}/api/generate",
            json={"model": self.model, "prompt": prompt, "stream": False},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.get("status_code", 500) != 200:
            raise RuntimeError(f"Model server returned {resp.get('status_code')}")
        return resp.get("json", {}).get("response", "")


class _RequestsHttpClient:
    """Thin wrapper so the adapter doesn't hard-depend on `requests`
    being imported at module load time in environments without it."""

    def get(self, url: str, timeout: float) -> dict:
        import urllib.request
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {"status_code": resp.status, "json": json.loads(resp.read() or b"{}")}

    def post(self, url: str, json: dict, timeout: float) -> dict:
        import urllib.request
        import json as json_mod
        data = json_mod.dumps(json).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST",
                                      headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {"status_code": resp.status, "json": json_mod.loads(resp.read() or b"{}")}
