import pytest
from backend.adapters.storage.sqlite_storage import SqliteStorageAdapter
from backend.models.recipe import Recipe, Outline, Slide, Theme, StructureSource


def make_recipe(project_id="p1"):
    outline = Outline(structure_source=StructureSource.RULE_BASED, slides=[
        Slide(order=1, title="Test Slide", content_blocks=[]),
    ])
    return Recipe.new(project_id=project_id, source_text="hello", outline=outline)


def test_save_and_get_recipe_roundtrip():
    storage = SqliteStorageAdapter(":memory:")
    recipe = make_recipe()
    project_id = storage.save_recipe("user1", recipe, "My Presentation")
    fetched = storage.get_recipe(project_id, "user1")
    assert fetched is not None
    assert fetched.source_text == "hello"
    assert fetched.outline.slides[0].title == "Test Slide"


def test_save_and_get_roundtrip_preserves_layout_type_and_image_query():
    """Regression test (ADR-038): layout_type and image_query were
    silently dropped on every load — reverted to their dataclass
    defaults ('bullet_list', None) the moment a saved project was
    fetched back, discarding real AI-planned layout/image work on
    every single re-export. The original roundtrip test above never
    set non-default values for either field, which is exactly how
    this went unnoticed."""
    storage = SqliteStorageAdapter(":memory:")
    outline = Outline(structure_source=StructureSource.AI_GENERATED, slides=[
        Slide(order=1, title="Revenue Growth", content_blocks=[],
              layout_type="statistics", image_query="growth chart"),
        Slide(order=2, title="Our Process", content_blocks=[],
              layout_type="process", image_query=None),
    ])
    recipe = Recipe.new(project_id="p2", source_text="hello", outline=outline)
    project_id = storage.save_recipe("user1", recipe, "My Presentation")

    fetched = storage.get_recipe(project_id, "user1")
    assert fetched.outline.slides[0].layout_type == "statistics"
    assert fetched.outline.slides[0].image_query == "growth chart"
    assert fetched.outline.slides[1].layout_type == "process"
    assert fetched.outline.slides[1].image_query is None


def test_owner_isolation_blocks_other_users():
    storage = SqliteStorageAdapter(":memory:")
    recipe = make_recipe()
    project_id = storage.save_recipe("user1", recipe, "Private Deck")
    # A different owner_id must not be able to fetch it — same "not
    # found" response as a nonexistent project, per Blueprint Section 11.
    result = storage.get_recipe(project_id, "user2")
    assert result is None


def test_list_projects_only_returns_owners_projects():
    storage = SqliteStorageAdapter(":memory:")
    storage.save_recipe("user1", make_recipe("p1"), "Deck A")
    storage.save_recipe("user2", make_recipe("p2"), "Deck B")
    user1_projects = storage.list_projects("user1")
    assert len(user1_projects) == 1
    assert user1_projects[0].title == "Deck A"


def test_delete_respects_ownership():
    storage = SqliteStorageAdapter(":memory:")
    project_id = storage.save_recipe("user1", make_recipe(), "Deck")
    assert storage.delete_recipe(project_id, "user2") is False  # wrong owner
    assert storage.delete_recipe(project_id, "user1") is True   # correct owner
    assert storage.get_recipe(project_id, "user1") is None
