"""
Tests for Phase 3.5 Tier 2 (ADR-025): Media Port and image integration.

Same FakeHttpClient mocking pattern as tests/contract/test_ai_port.py —
verifies the Unsplash adapter's request/response handling without a
real network call or a real API key.
"""

import pytest
from backend.adapters.media.null_media_adapter import NullMediaAdapter
from backend.adapters.media.unsplash_adapter import UnsplashMediaAdapter


class FakeHttpClient:
    def __init__(self, search_status=200, search_json=None, image_status=200, image_content=b"fake-image-bytes"):
        self.search_status = search_status
        self.search_json = search_json if search_json is not None else {
            "results": [{"urls": {"small": "https://images.unsplash.com/fake.jpg"}}]
        }
        self.image_status = image_status
        self.image_content = image_content
        self.calls = []

    def get(self, url, headers=None, timeout=10):
        self.calls.append(url)
        if "api.unsplash.com" in url:
            return {"status_code": self.search_status, "json": self.search_json, "content": b""}
        return {"status_code": self.image_status, "content": self.image_content, "json": None}


# -- NullMediaAdapter: always unavailable, always None -----------------

def test_null_media_adapter_always_unavailable():
    assert NullMediaAdapter().is_available() is False


def test_null_media_adapter_always_returns_none():
    assert NullMediaAdapter().search_image("mountains") is None


# -- UnsplashMediaAdapter: no key configured ---------------------------

def test_unsplash_unavailable_without_access_key():
    adapter = UnsplashMediaAdapter(access_key="", http_client=FakeHttpClient())
    assert adapter.is_available() is False
    assert adapter.search_image("mountains") is None


# -- UnsplashMediaAdapter: happy path -----------------------------------

def test_unsplash_available_with_access_key():
    adapter = UnsplashMediaAdapter(access_key="fake-key", http_client=FakeHttpClient())
    assert adapter.is_available() is True


def test_unsplash_returns_image_bytes_on_successful_search():
    client = FakeHttpClient()
    adapter = UnsplashMediaAdapter(access_key="fake-key", http_client=client)
    result = adapter.search_image("mountains")
    assert result == b"fake-image-bytes"
    # Confirms both calls actually happened — search, then image fetch.
    assert any("api.unsplash.com" in c for c in client.calls)
    assert any("images.unsplash.com" in c for c in client.calls)


# -- UnsplashMediaAdapter: graceful degradation on every failure mode --

def test_unsplash_returns_none_on_search_failure():
    client = FakeHttpClient(search_status=401)  # e.g. bad/revoked key
    adapter = UnsplashMediaAdapter(access_key="fake-key", http_client=client)
    assert adapter.search_image("mountains") is None


def test_unsplash_returns_none_on_empty_results():
    client = FakeHttpClient(search_json={"results": []})
    adapter = UnsplashMediaAdapter(access_key="fake-key", http_client=client)
    assert adapter.search_image("an extremely obscure query") is None


def test_unsplash_returns_none_on_image_download_failure():
    client = FakeHttpClient(image_status=500)
    adapter = UnsplashMediaAdapter(access_key="fake-key", http_client=client)
    assert adapter.search_image("mountains") is None


def test_unsplash_returns_none_on_empty_query():
    adapter = UnsplashMediaAdapter(access_key="fake-key", http_client=FakeHttpClient())
    assert adapter.search_image("") is None


def test_unsplash_never_raises_on_unexpected_client_exception():
    class BrokenClient:
        def get(self, *a, **k):
            raise ConnectionError("simulated network failure")

    adapter = UnsplashMediaAdapter(access_key="fake-key", http_client=BrokenClient())
    # Must degrade to None, never propagate the exception up and break generation.
    assert adapter.search_image("mountains") is None


# -- End-to-end: export pipeline actually embeds an image when available --

def test_export_embeds_image_when_media_adapter_available(monkeypatch):
    from backend.engines.generate import generate_presentation
    from backend.adapters import registry as reg
    from pptx import Presentation
    import io

    class FakeMediaAdapter:
        def is_available(self):
            return True

        def search_image(self, query):
            # A minimal, genuinely valid 1x1 PNG, so python-pptx can
            # actually embed it without erroring on a fake byte string.
            return bytes.fromhex(
                "89504e470d0a1a0a0000000d494844520000000100000001080600000"
                "01f15c4890000000a49444154789c6360000002000100ffff03000006"
                "000557bf0e0000000049454e44ae426082"
            )

    monkeypatch.setattr(reg, "get_media_adapter", lambda: FakeMediaAdapter())

    source = (
        "**Team Overview**\n\n"
        "**Our Culture**\n"
        "We value collaboration and continuous learning across every team.\n"
    ).encode("utf-8")

    recipe, pptx_bytes = generate_presentation(file_bytes=source, filename="team.txt", export_format="pptx")
    prs = Presentation(io.BytesIO(pptx_bytes))

    # Title slide should have an embedded picture.
    title_slide = prs.slides[0]
    pictures = [s for s in title_slide.shapes if s.shape_type == 13]  # MSO_SHAPE_TYPE.PICTURE == 13
    assert len(pictures) == 1


def test_export_unaffected_when_media_adapter_unavailable():
    """Confirms the default (NullMediaAdapter) path produces zero
    embedded images — the normal, current, $0-cost behavior."""
    from backend.engines.generate import generate_presentation
    from pptx import Presentation
    import io

    source = (
        "**Team Overview**\n\n"
        "**Our Culture**\n"
        "We value collaboration and continuous learning across every team.\n"
    ).encode("utf-8")

    recipe, pptx_bytes = generate_presentation(file_bytes=source, filename="team.txt", export_format="pptx")
    prs = Presentation(io.BytesIO(pptx_bytes))

    for slide in prs.slides:
        pictures = [s for s in slide.shapes if s.shape_type == 13]
        assert len(pictures) == 0
