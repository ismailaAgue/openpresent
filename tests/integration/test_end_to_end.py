from backend.engines.generate import generate_presentation


def test_full_flow_txt_to_pptx():
    source = (
        "The French Revolution\n"
        "The French Revolution began in 1789 and reshaped French society. "
        "It ended the absolute monarchy and introduced new ideas about citizenship and rights.\n\n"
        "Causes\n"
        "Economic hardship, social inequality, and Enlightenment ideas all contributed to unrest. "
        "The monarchy's failure to reform the tax system deepened public anger.\n\n"
        "Outcomes\n"
        "The revolution led to the rise of Napoleon and influenced revolutionary movements worldwide. "
        "It also established the Declaration of the Rights of Man.\n"
    ).encode("utf-8")

    recipe, pptx_bytes = generate_presentation(
        file_bytes=source,
        filename="history_essay.txt",
        export_format="pptx",
    )

    # The core thesis: this works completely without AI.
    assert recipe.outline.structure_source.value == "rule-based"
    assert len(recipe.outline.slides) >= 3
    assert pptx_bytes[:2] == b"PK"  # PPTX is a zip container
    assert len(pptx_bytes) > 1000  # not an empty/broken file
