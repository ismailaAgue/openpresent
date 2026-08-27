"""
Regression tests for ADR-034's Cloudflare/User-Agent fix — verifying
the REAL _post_json/get functions (not the injectable http_post fakes
used elsewhere, which bypass this code entirely) actually attach the
header to the real urllib.request.Request object. This is what
confirms the fix reaches the wire, not just that with_user_agent()
works in isolation (already covered in test_http_headers.py).
"""

from unittest.mock import patch, MagicMock
import json


def _fake_response(body: dict, status: int = 200):
    resp = MagicMock()
    resp.status = status
    resp.read.return_value = json.dumps(body).encode("utf-8")
    resp.headers = {"Content-Type": "application/json"}
    resp.__enter__ = lambda self: resp
    resp.__exit__ = lambda self, *a: None
    return resp


def test_gemini_post_json_sends_user_agent():
    from backend.adapters.ai.gemini_adapter import _post_json

    with patch("urllib.request.urlopen", return_value=_fake_response({"candidates": []})) as mock_urlopen:
        _post_json("https://generativelanguage.googleapis.com/fake", {"contents": []}, 10)
        request_obj = mock_urlopen.call_args[0][0]
        assert request_obj.get_header("User-agent") == "OpenPresent/1.0 (+https://github.com/ismailaAgue/openpresent)"


def test_openai_compatible_post_json_sends_user_agent_the_confirmed_groq_fix():
    """This is the exact confirmed fix for the production Groq 403/
    error-1010 failure — Cloudflare blocking urllib's default
    User-Agent before the request reached Groq's own API."""
    from backend.adapters.ai.openai_compatible_base import _post_json

    with patch("urllib.request.urlopen", return_value=_fake_response({"choices": []})) as mock_urlopen:
        _post_json("https://api.groq.com/openai/v1/chat/completions", "fake-key", {"model": "x"}, 10)
        request_obj = mock_urlopen.call_args[0][0]
        assert request_obj.get_header("User-agent") == "OpenPresent/1.0 (+https://github.com/ismailaAgue/openpresent)"


def test_media_http_client_get_sends_user_agent():
    from backend.adapters.media.http_client import UrllibHttpClient

    with patch("urllib.request.urlopen", return_value=_fake_response({"results": []})) as mock_urlopen:
        UrllibHttpClient().get("https://api.unsplash.com/fake")
        request_obj = mock_urlopen.call_args[0][0]
        assert request_obj.get_header("User-agent") == "OpenPresent/1.0 (+https://github.com/ismailaAgue/openpresent)"


def test_tavily_post_json_sends_user_agent():
    from backend.adapters.research.tavily_research import _post_json

    with patch("urllib.request.urlopen", return_value=_fake_response({"results": []})) as mock_urlopen:
        _post_json("https://api.tavily.com/search", {"query": "x"}, 10)
        request_obj = mock_urlopen.call_args[0][0]
        assert request_obj.get_header("User-agent") == "OpenPresent/1.0 (+https://github.com/ismailaAgue/openpresent)"


def test_with_user_agent_never_overrides_ddg_custom_user_agent():
    """DuckDuckGoResearchAdapter already sets its own descriptive
    User-Agent — with_user_agent's setdefault semantics mean this
    codebase's later addition of the shared header never clobbers a
    provider-specific one that was already there for a reason."""
    from backend.adapters.research.duckduckgo_research import DuckDuckGoResearchAdapter

    class CapturingClient:
        def get(self, url, headers=None, timeout=10):
            CapturingClient.last_headers = headers
            return {"status_code": 200, "content": b"<html></html>"}

    DuckDuckGoResearchAdapter(http_client=CapturingClient()).research("topic")
    assert CapturingClient.last_headers["User-Agent"] == "Mozilla/5.0 (compatible; OpenPresentResearch/1.0)"
