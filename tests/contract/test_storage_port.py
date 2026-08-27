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


# -- workspace_id (ADR-044) -----------------------------------------------

def test_save_recipe_with_workspace_id_is_reflected_in_list_projects():
    storage = SqliteStorageAdapter(":memory:")
    storage.save_recipe("user1", make_recipe("p1"), "Deck A", workspace_id="ws1")
    projects = storage.list_projects("user1")
    assert projects[0].workspace_id == "ws1"


def test_save_recipe_without_workspace_id_defaults_to_none():
    """Pre-ADR-044 behavior, unchanged: omitting workspace_id entirely
    saves an ungrouped project, same as before this field existed."""
    storage = SqliteStorageAdapter(":memory:")
    storage.save_recipe("user1", make_recipe("p1"), "Deck A")
    projects = storage.list_projects("user1")
    assert projects[0].workspace_id is None


def test_list_projects_filters_by_workspace_id():
    storage = SqliteStorageAdapter(":memory:")
    storage.save_recipe("user1", make_recipe("p1"), "In Workspace", workspace_id="ws1")
    storage.save_recipe("user1", make_recipe("p2"), "Ungrouped")
    storage.save_recipe("user1", make_recipe("p3"), "Different Workspace", workspace_id="ws2")

    ws1_only = storage.list_projects("user1", workspace_id="ws1")
    assert len(ws1_only) == 1
    assert ws1_only[0].title == "In Workspace"

    everything = storage.list_projects("user1")  # no filter -> pre-ADR-044 behavior, sees all 3
    assert len(everything) == 3


def test_re_saving_an_existing_project_without_workspace_id_does_not_unassign_it():
    """A slide edit (re-save of an existing project) must never
    silently un-assign a project from its workspace just because the
    edit call site doesn't happen to know/pass workspace_id."""
    storage = SqliteStorageAdapter(":memory:")
    recipe = make_recipe("p1")
    storage.save_recipe("user1", recipe, "Deck A", workspace_id="ws1")

    storage.save_recipe("user1", recipe, "Deck A (edited)")  # no workspace_id passed this time

    projects = storage.list_projects("user1")
    assert projects[0].workspace_id == "ws1"  # still assigned, not wiped out
    assert projects[0].title == "Deck A (edited)"  # the actual edit did apply


def test_re_saving_with_a_new_workspace_id_does_reassign_it():
    storage = SqliteStorageAdapter(":memory:")
    recipe = make_recipe("p1")
    storage.save_recipe("user1", recipe, "Deck A", workspace_id="ws1")
    storage.save_recipe("user1", recipe, "Deck A", workspace_id="ws2")
    assert storage.list_projects("user1")[0].workspace_id == "ws2"


def test_unassign_workspace_clears_workspace_id_on_matching_projects():
    storage = SqliteStorageAdapter(":memory:")
    storage.save_recipe("user1", make_recipe("p1"), "Deck A", workspace_id="ws1")
    storage.save_recipe("user1", make_recipe("p2"), "Deck B", workspace_id="ws1")
    storage.save_recipe("user1", make_recipe("p3"), "Deck C", workspace_id="ws2")

    storage.unassign_workspace("ws1", "user1")

    projects_by_title = {p.title: p.workspace_id for p in storage.list_projects("user1")}
    assert projects_by_title["Deck A"] is None
    assert projects_by_title["Deck B"] is None
    assert projects_by_title["Deck C"] == "ws2"  # untouched — different workspace


def test_unassign_workspace_respects_ownership():
    """Must not be possible to unassign another user's projects by
    guessing/reusing a workspace_id string."""
    storage = SqliteStorageAdapter(":memory:")
    storage.save_recipe("user1", make_recipe("p1"), "Deck A", workspace_id="ws1")

    storage.unassign_workspace("ws1", "user2")  # wrong owner — must be a no-op

    assert storage.list_projects("user1")[0].workspace_id == "ws1"  # untouched


def test_unassign_workspace_with_no_matching_projects_is_a_silent_no_op():
    storage = SqliteStorageAdapter(":memory:")
    storage.unassign_workspace("nonexistent-workspace", "user1")  # must not raise
