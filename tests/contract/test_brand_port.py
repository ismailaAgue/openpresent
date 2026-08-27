"""Contract tests for BrandProfilePort / SqliteBrandAdapter (ADR-045)."""

from backend.adapters.brand.sqlite_adapter import SqliteBrandAdapter
from backend.ports.brand import BrandProfile


def make_brand_adapter():
    return SqliteBrandAdapter(":memory:")


def test_set_then_get():
    b = make_brand_adapter()
    b.set_brand_profile("ws1", "user1", name="Acme", colors="Blue and purple", tone="Professional")
    profile = b.get_brand_profile("ws1", "user1")
    assert profile is not None
    assert profile.name == "Acme"
    assert profile.colors == "Blue and purple"
    assert profile.tone == "Professional"


def test_get_returns_none_when_never_set():
    b = make_brand_adapter()
    assert b.get_brand_profile("ws1", "user1") is None


def test_get_returns_none_for_wrong_owner():
    b = make_brand_adapter()
    b.set_brand_profile("ws1", "user1", name="Acme")
    assert b.get_brand_profile("ws1", "user2") is None


def test_set_is_an_upsert_and_a_whole_record_replace():
    """Second call for the same workspace overwrites, and fields
    omitted on the second call revert to blank rather than keeping
    the first call's values — a whole-record replace, not a merge."""
    b = make_brand_adapter()
    b.set_brand_profile("ws1", "user1", name="Acme", colors="Blue")
    b.set_brand_profile("ws1", "user1", tone="Playful")  # name/colors NOT re-sent this time

    profile = b.get_brand_profile("ws1", "user1")
    assert profile.tone == "Playful"
    assert profile.name == ""     # wiped, not preserved from the first call
    assert profile.colors == ""   # wiped, not preserved from the first call


def test_created_at_is_preserved_across_updates():
    b = make_brand_adapter()
    first = b.set_brand_profile("ws1", "user1", name="Acme")
    second = b.set_brand_profile("ws1", "user1", name="Acme Renamed")
    assert second.created_at == first.created_at
    assert second.updated_at >= first.updated_at


def test_delete_brand_profile():
    b = make_brand_adapter()
    b.set_brand_profile("ws1", "user1", name="Acme")
    deleted = b.delete_brand_profile("ws1", "user1")
    assert deleted is True
    assert b.get_brand_profile("ws1", "user1") is None


def test_delete_wrong_owner_returns_false_and_does_not_delete():
    b = make_brand_adapter()
    b.set_brand_profile("ws1", "user1", name="Acme")
    deleted = b.delete_brand_profile("ws1", "user2")
    assert deleted is False
    assert b.get_brand_profile("ws1", "user1") is not None


def test_delete_nonexistent_returns_false_not_raise():
    b = make_brand_adapter()
    assert b.delete_brand_profile("nonexistent-ws", "user1") is False


def test_different_workspaces_have_independent_profiles():
    b = make_brand_adapter()
    b.set_brand_profile("ws1", "user1", name="Acme")
    b.set_brand_profile("ws2", "user1", name="Beta Corp")
    assert b.get_brand_profile("ws1", "user1").name == "Acme"
    assert b.get_brand_profile("ws2", "user1").name == "Beta Corp"


# -- BrandProfile.is_empty() (used to skip prompt injection) --------------

def test_is_empty_true_for_default_profile():
    assert BrandProfile(workspace_id="ws1", owner_id="user1").is_empty() is True


def test_is_empty_false_if_any_single_field_is_set():
    assert BrandProfile(workspace_id="ws1", owner_id="user1", tone="Playful").is_empty() is False
