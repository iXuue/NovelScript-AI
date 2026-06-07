from types import SimpleNamespace

from app.services.scene_plan_service import _validate_chapter_scene_plan_payload


def test_chapter_scene_plan_string_list_fields_are_normalized():
    chapter = SimpleNamespace(chapter_id="CH001")
    paragraphs = [SimpleNamespace(paragraph_id="CH001_P001")]

    scenes = _validate_chapter_scene_plan_payload(
        {
            "scenes": [
                {
                    "title": "雨夜归来",
                    "source_paragraph_ids": "CH001_P001",
                    "interior_exterior": "外景",
                    "location": "旧宅门口",
                    "time": "夜",
                    "characters": "她",
                    "must_cover_plot": "她回到旧宅",
                    "must_keep_dialogue": "",
                    "must_keep_visual_elements": "雨夜和旧宅门口",
                    "must_keep_foreshadowing": None,
                    "scene_function": "建立回归和悬念",
                    "core_conflict": "她是否进入旧宅",
                    "adaptation_note": "把雨夜作为视觉压力。",
                }
            ]
        },
        chapter,
        paragraphs,
    )

    assert scenes[0]["source_paragraph_ids"] == ["CH001_P001"]
    assert scenes[0]["characters"] == ["她"]
    assert scenes[0]["must_cover_plot"] == ["她回到旧宅"]
    assert scenes[0]["must_keep_dialogue"] == []
    assert scenes[0]["must_keep_visual_elements"] == ["雨夜和旧宅门口"]
    assert scenes[0]["must_keep_foreshadowing"] == []
