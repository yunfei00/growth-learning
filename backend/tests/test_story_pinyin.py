from app.services.story_pinyin import annotate_paragraph_pinyin, first_contextual_readings


def test_story_pinyin_covers_out_of_catalog_characters_and_punctuation() -> None:
    text = "小猫来到窗边。"
    annotated = annotate_paragraph_pinyin(text)

    assert len(annotated) == len(text)
    assert annotated[text.index("边")] == "biān"
    assert annotated[-1] is None


def test_story_pinyin_uses_context_for_structural_de() -> None:
    text = "太阳暖暖的，小猫开心地坐下来。"
    annotated = annotate_paragraph_pinyin(text)

    assert annotated[text.index("地")] == "de"
    readings = first_contextual_readings([text])
    assert readings["地"] == "de"
