"""
Shared outbound HTTP headers — ADR-034.

Production bug: Python's urllib sends "Python-urllib/x.y" as its
default User-Agent, which Cloudflare's Bot Management (used by Groq
and many other API providers) treats as an unambiguous bot signature
and blocks outright with a 403/error-1010 — before the request ever
reaches the provider's own API logic. Confirmed via Groq's own
community forum: adding a real User-Agent header is the documented
fix. Applied to every outbound request this codebase makes (not just
Groq) since the same Cloudflare-fingerprinting risk applies to any
provider behind it, and there's no downside to always identifying
honestly as what this actually is.
"""

USER_AGENT = "OpenPresent/1.0 (+https://github.com/ismailaAgue/openpresent)"


def with_user_agent(headers: dict | None = None) -> dict:
    merged = dict(headers or {})
    merged.setdefault("User-Agent", USER_AGENT)
    return merged
