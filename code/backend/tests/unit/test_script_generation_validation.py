import pytest

from app.services.script_service import _validate_script_scene_payload


class SceneStub:
    scene_id = "S001"
    title = "雨夜归来"
    source_chapter_ids = ["CH001"]
    characters = ["她"]
    scene_function = "建立人物回归"
    core_conflict = "她是否进入旧宅"


def test_dialogue_block_requires_speaker():
    payload = {
        "scene_id": "S001",
        "title": "雨夜归来",
        "content_blocks": [
            {
                "content_block_id": "CB001",
                "type": "dialogue",
                "text": "她回来了。",
                "speaker": None,
                "source_evidence_ids": ["EV001"],
            }
        ],
    }

    with pytest.raises(RuntimeError, match="dialogue block requires speaker"):
        _validate_script_scene_payload(payload, SceneStub(), {"EV001"})


def test_invalid_block_type_is_rejected():
    payload = {
        "scene_id": "S001",
        "title": "雨夜归来",
        "content_blocks": [
            {
                "content_block_id": "CB001",
                "type": "not_a_real_type",
                "text": "她想起那封旧信。",
                "speaker": None,
                "source_evidence_ids": ["EV001"],
            }
        ],
    }

    with pytest.raises(RuntimeError, match="block type is invalid"):
        _validate_script_scene_payload(payload, SceneStub(), {"EV001"})
