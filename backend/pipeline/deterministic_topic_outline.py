"""
Deterministic topic outline — ADR-028.

The topic-first equivalent of RuleBasedStructureAdapter for the
document-upload flow: what "AI pauses, generation continues"
(Constitution Principle 3) means when there's no source document to
fall back on. Not a great deck — there's no way to be substantive
about an unknown topic without an AI call or a source document — but
it is a real, valid, exportable presentation with a sensible generic
narrative shape, so the product never hard-fails just because no AI
provider is configured or reachable.
"""

from backend.models.recipe import Outline, Slide, ContentBlock, BlockType, StructureSource
from backend.ports.ai_pipeline import GenerationRequest

_GENERIC_SECTIONS = [
    "Background", "Key Points", "Why It Matters", "Current State",
    "Challenges", "Opportunities", "Approach", "Details", "Examples",
    "Considerations", "Impact", "Looking Ahead",
]


def build_deterministic_outline(request: GenerationRequest) -> Outline:
    slide_count = max(3, request.slide_count)
    topic = request.topic.strip() or "Presentation"

    slides = [Slide(
        order=1, title=topic,
        content_blocks=[ContentBlock(type=BlockType.BULLET, text=f"An overview of {topic}")],
    )]

    body_slots = slide_count - 2  # minus title slide and closing slide
    for i in range(max(0, body_slots)):
        section = _GENERIC_SECTIONS[i % len(_GENERIC_SECTIONS)]
        slides.append(Slide(
            order=len(slides) + 1,
            title=f"{section}",
            content_blocks=[
                ContentBlock(type=BlockType.BULLET, text=f"{section} relevant to {topic}"),
                ContentBlock(type=BlockType.BULLET, text="Add your specific details here"),
                ContentBlock(type=BlockType.NOTE,
                              text=f"Expand on {section.lower()} as it relates to {topic}."),
            ],
        ))

    slides.append(Slide(
        order=len(slides) + 1, title="Thank You",
        content_blocks=[ContentBlock(type=BlockType.BULLET, text="Questions?")],
    ))

    return Outline(structure_source=StructureSource.DETERMINISTIC_TOPIC, slides=slides,
                    document_type="ai_topic")
