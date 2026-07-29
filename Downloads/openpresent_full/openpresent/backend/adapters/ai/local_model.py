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
from backend.models.recipe import Outline, Slide, ContentBlock, BlockType, StructureSource

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:3b"
HEALTH_CHECK_TIMEOUT = 1.5
REQUEST_TIMEOUT = 30


class LocalModelAdapter(AIPort):
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

        prompt = self._build_structure_prompt(outline, source_text)
        try:
            raw = self._generate(prompt)
            improved = self._parse_outline_response(raw, fallback=outline)
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

    def _build_structure_prompt(self, outline: Outline, source_text: str) -> str:
        slide_titles = [s.title for s in outline.slides]
        return (
            "You are improving a presentation outline generated from a student's "
            "document. Current slide titles: " + ", ".join(slide_titles) + ". "
            "Respond ONLY with valid JSON: a list of objects with 'title' and "
            "'bullets' (list of strings). Base it on this source text: " + source_text[:2000]
        )

    def _parse_outline_response(self, raw: str, fallback: Outline) -> Outline:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return fallback  # malformed model output -> keep the rule-based baseline

        if not isinstance(data, list) or not data:
            return fallback

        slides = []
        for i, item in enumerate(data):
            if not isinstance(item, dict) or "title" not in item:
                return fallback  # any malformed entry -> discard the whole AI attempt, don't half-apply it
            bullets = item.get("bullets", [])
            slides.append(Slide(
                order=i + 1,
                title=str(item["title"]),
                content_blocks=[ContentBlock(type=BlockType.BULLET, text=str(b)) for b in bullets],
            ))
        return Outline(structure_source=StructureSource.AI_ENHANCED, slides=slides)


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
