"""
Root conftest — hermetic-by-default registry state (ADR-037).

Real bug this fixes: `registry.get_media_adapter()` and
`get_research_adapter()` both include Wikimedia/Wikipedia in their
DEFAULT provider list unconditionally — no API key required, by
deliberate design (ADR-029/030's "universal fallback, no key needed"
decision). Several tests assumed "no keys configured" meant "zero
network calls" and never explicitly mocked these two functions. That
assumption was only ever true by ACCIDENT: this sandboxed development
environment has no network route to wikipedia.org/wikimedia.org at
all, so those real calls silently failed and looked like "no
provider configured" — the right answer for the wrong reason. On a
real network (GitHub Actions runners), the same calls succeed, and a
test asserting "zero images embedded" broke in CI while passing
locally, which is exactly the gap this fixture closes.

This is an autouse, function-scoped fixture applied to every test
under tests/ EXCEPT tests/smoke/ — live provider drift checks
(tests/smoke/test_live_provider_drift.py) deliberately construct
adapters directly (e.g. `GeminiAdapter(api_key=os.environ[...])`),
bypassing the registry entirely, so this fixture has no effect on them
either way; the explicit skip below exists for clarity of intent, not
because it's strictly required for correctness.

Individual tests remain free to override any of these three functions
with their own monkeypatch.setattr call (as many already do, e.g.
test_media_port.py's FakeMediaAdapter tests) — a test's own patch,
applied within the test body, simply overrides this fixture's
baseline for that one test, exactly as before.
"""

import pytest
from backend.adapters import registry


@pytest.fixture(autouse=True)
def _hermetic_registry_defaults(monkeypatch, request):
    if "tests/smoke" in str(request.node.fspath).replace("\\", "/"):
        yield
        return

    monkeypatch.setattr(registry, "get_ai_adapter", lambda: registry.NullAdapter())
    monkeypatch.setattr(registry, "get_media_adapter", lambda: registry.NullMediaAdapter())
    monkeypatch.setattr(registry, "get_research_adapter", lambda: registry.NullResearchAdapter())
    yield
