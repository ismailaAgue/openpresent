import pytest
from backend.adapters import registry
from backend.models.recipe import Recipe, Outline, Slide, ContentBlock, BlockType, StructureSource
from backend.engines import edit_slide
from backend.engines.edit_slide import (
    edit_slide_manually, regenerate_slide_ai,
    ProjectNotFoundError, SlideNotFoundError, AIUnavailableError,
)


@pytest.fixture(autouse=True)
def reset_storage_singleton():
    registry._storage_adapter_instance = None
    yield
    registry._storage_adapter_instance = None


def make_and_save_project(owner_id="user1"):
    outline = Outline(structure_source=StructureSource.AI_GENERATED, slides=[
        Slide(order=1, title="Introduction", content_blocks=[
            ContentBlock(type=BlockType.BULLET, text="Welcome"),
        ]),
        Slide(order=2, title="Effects on Agriculture", content_blocks=[
            ContentBlock(type=BlockType.BULLET, text="Crop yields declining"),
            ContentBlock(type=BlockType.BULLET, text="Water scarcity increasing"),
            ContentBlock(type=BlockType.NOTE, text="Discuss regional variation."),
        ], layout_type="statistics", image_query="agriculture drought"),
        Slide(order=3, title="Conclusion", content_blocks=[
            ContentBlock(type=BlockType.BULLET, text="Thank you"),
        ]),
    ])
    recipe = Recipe.new(project_id="proj1", source_text="Topic: Climate Change", outline=outline,
                         audience_type="general", language="en")
    storage = registry.get_storage_adapter()
    project_id = storage.save_recipe(owner_id, recipe, "Climate Change")
    return project_id


# -- Manual editing --------------------------------------------------------

def test_edit_slide_manually_updates_title():
    project_id = make_and_save_project()
    recipe = edit_slide_manually(project_id, 2, "user1", title="Agricultural Impact")
    assert recipe.outline.slides[1].title == "Agricultural Impact"


def test_edit_slide_manually_updates_bullets_only():
    project_id = make_and_save_project()
    recipe = edit_slide_manually(project_id, 2, "user1", bullets=["New point one", "New point two"])
    slide = recipe.outline.slides[1]
    bullets = [b.text for b in slide.content_blocks if b.type == BlockType.BULLET]
    assert bullets == ["New point one", "New point two"]
    # Notes must survive a bullets-only edit — only bullets were targeted.
    notes = [b.text for b in slide.content_blocks if b.type == BlockType.NOTE]
    assert notes == ["Discuss regional variation."]


def test_edit_slide_manually_updates_notes_only():
    project_id = make_and_save_project()
    recipe = edit_slide_manually(project_id, 2, "user1", notes="New speaker note.")
    slide = recipe.outline.slides[1]
    notes = [b.text for b in slide.content_blocks if b.type == BlockType.NOTE]
    assert notes == ["New speaker note."]
    bullets = [b.text for b in slide.content_blocks if b.type == BlockType.BULLET]
    assert bullets == ["Crop yields declining", "Water scarcity increasing"]  # untouched


def test_edit_slide_manually_leaves_layout_type_and_image_query_untouched():
    project_id = make_and_save_project()
    recipe = edit_slide_manually(project_id, 2, "user1", title="New Title")
    slide = recipe.outline.slides[1]
    assert slide.layout_type == "statistics"
    assert slide.image_query == "agriculture drought"


def test_edit_slide_manually_does_not_touch_other_slides():
    project_id = make_and_save_project()
    recipe = edit_slide_manually(project_id, 2, "user1", title="New Title")
    assert recipe.outline.slides[0].title == "Introduction"
    assert recipe.outline.slides[2].title == "Conclusion"


def test_edit_slide_manually_persists_across_reload():
    project_id = make_and_save_project()
    edit_slide_manually(project_id, 2, "user1", title="Persisted Title")
    storage = registry.get_storage_adapter()
    reloaded = storage.get_recipe(project_id, "user1")
    assert reloaded.outline.slides[1].title == "Persisted Title"


def test_edit_slide_manually_requires_at_least_one_field():
    project_id = make_and_save_project()
    with pytest.raises(ValueError):
        edit_slide_manually(project_id, 2, "user1")


def test_edit_slide_manually_raises_on_unknown_project():
    with pytest.raises(ProjectNotFoundError):
        edit_slide_manually("not-a-real-project", 1, "user1", title="X")


def test_edit_slide_manually_raises_on_unknown_slide():
    project_id = make_and_save_project()
    with pytest.raises(SlideNotFoundError):
        edit_slide_manually(project_id, 999, "user1", title="X")


def test_edit_slide_manually_respects_ownership():
    project_id = make_and_save_project(owner_id="user1")
    with pytest.raises(ProjectNotFoundError):
        edit_slide_manually(project_id, 1, "someone_else", title="Hijacked")


# -- AI-assisted regeneration -----------------------------------------------

def test_regenerate_slide_ai_raises_when_no_ai_configured(monkeypatch):
    monkeypatch.setattr(registry, "get_ai_pipeline_adapter", lambda: registry._NullPipelineAdapter())
    project_id = make_and_save_project()
    with pytest.raises(AIUnavailableError):
        regenerate_slide_ai(project_id, 2, "user1")


def test_regenerate_slide_ai_updates_only_the_target_slide(monkeypatch):
    class FakePipeline:
        def is_available(self):
            return True

        def regenerate_slide(self, context):
            assert context.current_title == "Effects on Agriculture"
            assert "Introduction" in context.other_slide_titles
            assert "Conclusion" in context.other_slide_titles
            return ("Effects on Global Food Security",
                    ["Crop yields declining globally", "Water scarcity rising"],
                    "Updated speaker notes.")

    monkeypatch.setattr(registry, "get_ai_pipeline_adapter", lambda: FakePipeline())
    project_id = make_and_save_project()

    recipe = regenerate_slide_ai(project_id, 2, "user1", instructions="broaden the scope")

    edited = recipe.outline.slides[1]
    assert edited.title == "Effects on Global Food Security"
    bullets = [b.text for b in edited.content_blocks if b.type == BlockType.BULLET]
    assert bullets == ["Crop yields declining globally", "Water scarcity rising"]
    notes = [b.text for b in edited.content_blocks if b.type == BlockType.NOTE]
    assert notes == ["Updated speaker notes."]

    # Other slides completely untouched.
    assert recipe.outline.slides[0].title == "Introduction"
    assert recipe.outline.slides[2].title == "Conclusion"


def test_regenerate_slide_ai_leaves_layout_type_and_image_query_untouched(monkeypatch):
    """Documented scope boundary (ADR-038): regeneration only touches
    content, never layout_type/image_query, even though the new
    content could theoretically warrant a different layout."""
    class FakePipeline:
        def is_available(self):
            return True

        def regenerate_slide(self, context):
            return ("New Title", ["a", "b"], "notes")

    monkeypatch.setattr(registry, "get_ai_pipeline_adapter", lambda: FakePipeline())
    project_id = make_and_save_project()
    recipe = regenerate_slide_ai(project_id, 2, "user1")
    edited = recipe.outline.slides[1]
    assert edited.layout_type == "statistics"
    assert edited.image_query == "agriculture drought"


def test_regenerate_slide_ai_raises_and_logs_on_pipeline_failure(monkeypatch):
    captured = {}

    def fake_capture_exception(exc, tags=None):
        captured["exc"] = exc
        captured["tags"] = tags

    class FailingPipeline:
        def is_available(self):
            return True

        def regenerate_slide(self, context):
            raise RuntimeError("provider exploded")

    monkeypatch.setattr(registry, "get_ai_pipeline_adapter", lambda: FailingPipeline())
    monkeypatch.setattr(edit_slide, "capture_exception", fake_capture_exception)

    project_id = make_and_save_project()
    with pytest.raises(AIUnavailableError):
        regenerate_slide_ai(project_id, 2, "user1")

    assert captured.get("exc") is not None
    assert captured["tags"]["stage"] == "slide_regeneration"


def test_regenerate_slide_ai_respects_ownership(monkeypatch):
    class FakePipeline:
        def is_available(self):
            return True

    monkeypatch.setattr(registry, "get_ai_pipeline_adapter", lambda: FakePipeline())
    project_id = make_and_save_project(owner_id="user1")
    with pytest.raises(ProjectNotFoundError):
        regenerate_slide_ai(project_id, 1, "someone_else")


def test_regenerate_slide_ai_raises_on_unknown_slide(monkeypatch):
    class FakePipeline:
        def is_available(self):
            return True

        def regenerate_slide(self, context):
            return ("T", ["a"], "n")

    monkeypatch.setattr(registry, "get_ai_pipeline_adapter", lambda: FakePipeline())
    project_id = make_and_save_project()
    with pytest.raises(SlideNotFoundError):
        regenerate_slide_ai(project_id, 999, "user1")
