"""
registry.get_ai_adapter()'s own env-var-driven selection logic —
explicit single-provider choice and the "auto" composite cascade.

No prior test file covered this directly (confirmed by search before
writing these — test_conftest_hermeticity.py only checks the DEFAULT
outcome with nothing configured; nothing exercised the actual
branching logic deciding which adapter(s) get built from which env
vars). ADR-075 added 3 new free providers to this same function, which
is as good a reason as any to close this real, pre-existing gap while
touching the code anyway.
"""

import pytest
from backend.adapters import registry
from backend.adapters.ai.mistral_adapter import MistralAdapter
from backend.adapters.ai.cerebras_adapter import CerebrasAdapter
from backend.adapters.ai.cohere_adapter import CohereAdapter
from backend.adapters.ai.groq_adapter import GroqAdapter
from backend.adapters.ai.composite_adapter import CompositeAIAdapter
from backend.adapters.ai.null_adapter import NullAdapter

# Captured at import time, before any test runs — the real, undecorated
# function. The root conftest's autouse _hermetic_registry_defaults
# fixture replaces registry.get_ai_adapter with a lambda that always
# returns NullAdapter, for every test by default (ADR-037) — exactly
# the right default for tests that don't care about AI selection, but
# it means these tests, whose entire point IS exercising the real
# selection logic, need to explicitly restore the true implementation
# first or they'd just be testing the hermeticity lambda instead.
_real_get_ai_adapter = registry.get_ai_adapter


@pytest.fixture(autouse=True)
def reset_ai_adapter_singleton(monkeypatch):
    registry._ai_adapter_instance = None
    monkeypatch.setattr(registry, "get_ai_adapter", _real_get_ai_adapter)
    yield
    registry._ai_adapter_instance = None


def _clear_all_provider_env(monkeypatch):
    for var in ("OPENPRESENT_AI_ADAPTER", "OPENPRESENT_AI_BASE_URL", "GEMINI_API_KEY",
                "GROQ_API_KEY", "OPENROUTER_API_KEY", "HUGGINGFACE_API_KEY",
                "MISTRAL_API_KEY", "CEREBRAS_API_KEY", "COHERE_API_KEY"):
        monkeypatch.delenv(var, raising=False)


# -- Explicit single-provider selection (OPENPRESENT_AI_ADAPTER=...) ------

def test_explicit_mistral_selection(monkeypatch):
    _clear_all_provider_env(monkeypatch)
    monkeypatch.setenv("OPENPRESENT_AI_ADAPTER", "mistral")
    monkeypatch.setenv("MISTRAL_API_KEY", "fake-key")
    assert isinstance(registry.get_ai_adapter(), MistralAdapter)


def test_explicit_cerebras_selection(monkeypatch):
    _clear_all_provider_env(monkeypatch)
    monkeypatch.setenv("OPENPRESENT_AI_ADAPTER", "cerebras")
    monkeypatch.setenv("CEREBRAS_API_KEY", "fake-key")
    assert isinstance(registry.get_ai_adapter(), CerebrasAdapter)


def test_explicit_cohere_selection(monkeypatch):
    _clear_all_provider_env(monkeypatch)
    monkeypatch.setenv("OPENPRESENT_AI_ADAPTER", "cohere")
    monkeypatch.setenv("COHERE_API_KEY", "fake-key")
    assert isinstance(registry.get_ai_adapter(), CohereAdapter)


def test_explicit_selection_with_no_key_is_unavailable_not_an_error(monkeypatch):
    """Forcing a provider with no key configured must not crash —
    is_available() just correctly reports False, same contract every
    other adapter in this file already honors."""
    _clear_all_provider_env(monkeypatch)
    monkeypatch.setenv("OPENPRESENT_AI_ADAPTER", "cerebras")
    adapter = registry.get_ai_adapter()
    assert isinstance(adapter, CerebrasAdapter)
    assert adapter.is_available() is False


# -- Auto mode: the 3 new providers join the composite cascade -----------

def test_auto_mode_includes_mistral_when_key_is_set(monkeypatch):
    _clear_all_provider_env(monkeypatch)
    monkeypatch.setenv("MISTRAL_API_KEY", "fake-key")
    adapter = registry.get_ai_adapter()
    assert isinstance(adapter, CompositeAIAdapter)
    assert any(isinstance(a, MistralAdapter) for a in adapter.adapters)


def test_auto_mode_includes_cerebras_when_key_is_set(monkeypatch):
    _clear_all_provider_env(monkeypatch)
    monkeypatch.setenv("CEREBRAS_API_KEY", "fake-key")
    adapter = registry.get_ai_adapter()
    assert isinstance(adapter, CompositeAIAdapter)
    assert any(isinstance(a, CerebrasAdapter) for a in adapter.adapters)


def test_auto_mode_includes_cohere_when_key_is_set(monkeypatch):
    _clear_all_provider_env(monkeypatch)
    monkeypatch.setenv("COHERE_API_KEY", "fake-key")
    adapter = registry.get_ai_adapter()
    assert isinstance(adapter, CompositeAIAdapter)
    assert any(isinstance(a, CohereAdapter) for a in adapter.adapters)


def test_auto_mode_combines_new_and_pre_existing_providers(monkeypatch):
    """The 3 new providers must join the SAME composite as the
    pre-existing ones, not silently replace or exclude them — the
    whole point of the "AI shortage" fix is MORE fallback capacity,
    not a swap."""
    _clear_all_provider_env(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "fake-key-1")
    monkeypatch.setenv("CEREBRAS_API_KEY", "fake-key-2")
    monkeypatch.setenv("MISTRAL_API_KEY", "fake-key-3")
    monkeypatch.setenv("COHERE_API_KEY", "fake-key-4")
    adapter = registry.get_ai_adapter()
    assert isinstance(adapter, CompositeAIAdapter)
    kinds = {type(a) for a in adapter.adapters}
    assert kinds == {GroqAdapter, CerebrasAdapter, MistralAdapter, CohereAdapter}


def test_auto_mode_prioritizes_groq_and_cerebras_ahead_of_cohere():
    """ADR-075's stated priority reasoning (most generous free-tier
    capacity first) should actually be reflected in the composite's
    adapter order, not just described in a docstring nobody checks."""
    import os
    from unittest import mock
    env = {"GROQ_API_KEY": "k1", "CEREBRAS_API_KEY": "k2", "COHERE_API_KEY": "k3"}
    with mock.patch.dict(os.environ, env, clear=False):
        for var in ("OPENPRESENT_AI_ADAPTER", "OPENPRESENT_AI_BASE_URL", "GEMINI_API_KEY",
                    "MISTRAL_API_KEY", "OPENROUTER_API_KEY", "HUGGINGFACE_API_KEY"):
            os.environ.pop(var, None)
        registry._ai_adapter_instance = None
        adapter = registry.get_ai_adapter()
        kinds_in_order = [type(a).__name__ for a in adapter.adapters]
        assert kinds_in_order.index("GroqAdapter") < kinds_in_order.index("CohereAdapter")
        assert kinds_in_order.index("CerebrasAdapter") < kinds_in_order.index("CohereAdapter")


def test_auto_mode_with_nothing_configured_is_still_null(monkeypatch):
    """No regression: adding 3 new checks to the auto-mode branch must
    not change the "nothing configured" outcome."""
    _clear_all_provider_env(monkeypatch)
    assert isinstance(registry.get_ai_adapter(), NullAdapter)
