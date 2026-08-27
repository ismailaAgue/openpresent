"""Shared stdlib-only HTTP GET client — same choice as every other
adapter in this codebase (LocalModelAdapter, GeminiAdapter): no new
dependency for a simple GET+JSON pattern."""

import json as _json
import urllib.parse
import urllib.request
from backend.adapters.http_headers import with_user_agent


class UrllibHttpClient:
    def get(self, url: str, headers: dict | None = None, timeout: float = 10) -> dict:
        # ADR-034: always sends a real User-Agent — Cloudflare (used by
        # several of these providers) blocks urllib's default one
        # outright. See backend/adapters/http_headers.py.
        req = urllib.request.Request(url, headers=with_user_agent(headers), method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read()
            content_type = resp.headers.get("Content-Type", "")
            parsed_json = None
            if "application/json" in content_type:
                try:
                    parsed_json = _json.loads(content)
                except Exception:
                    parsed_json = None
            return {"status_code": resp.status, "content": content, "json": parsed_json}


def url_quote(s: str) -> str:
    return urllib.parse.quote(s)
