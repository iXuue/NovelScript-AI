from app.services.scene_plan_service import _validate_chapter_scene_plan_payload, _validate_scene_plan_payload


class ChapterStub:
    chapter_id = "CH001"


class ParagraphStub:
    def __init__(self, paragraph_id: str) -> None:
        self.paragraph_id = paragraph_id


def _scene_payload(source_paragraph_ids: list[str]) -> dict:
    return {
        "title": "Rainy Return",
        "source_paragraph_ids": source_paragraph_ids,
        "interior_exterior": "EXT",
        "location": "Old house gate",
        "time": "Night",
        "characters": ["She"],
        "must_cover_plot": ["She returns"],
        "must_keep_dialogue": [],
        "must_keep_visual_elements": ["Rain"],
        "must_keep_foreshadowing": [],
        "scene_function": "Open the story",
        "core_conflict": "Whether she enters",
        "adaptation_note": "Keep it concise.",
    }


def test_chapter_scene_plan_source_paragraph_ids_are_normalized():
    payload = {"scenes": [_scene_payload(["CH1_P11"])]}

    scenes = _validate_chapter_scene_plan_payload(payload, ChapterStub(), [ParagraphStub("CH001_P011")])

    assert scenes[0]["source_paragraph_ids"] == ["CH001_P011"]


def test_scene_plan_source_paragraph_ids_are_normalized():
    scene = {
        **_scene_payload(["CH1_P11"]),
        "scene_id": "S001",
        "order": 1,
        "source_chapter_ids": ["CH001"],
        "source_evidence_ids": [],
    }

    payload = _validate_scene_plan_payload({"scenes": [scene]}, {"CH001"}, {"CH001_P011"})

    assert payload["scenes"][0]["source_paragraph_ids"] == ["CH001_P011"]
