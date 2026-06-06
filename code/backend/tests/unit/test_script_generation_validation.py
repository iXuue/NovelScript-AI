import pytest

from app.services.script_service import _validate_script_scene_payload


class SceneStub:
    scene_id = "S001"
    title = "Rainy Return"
    source_chapter_ids = ["CH001"]
    source_paragraph_ids = ["CH001_P001"]
    characters = ["She"]
    scene_function = "Establish the protagonist's return"
    core_conflict = "Whether she enters the old house"


def test_dialogue_block_requires_speaker():
    payload = {
        "scene_id": "S001",
        "title": "Rainy Return",
        "content_blocks": [
            {
                "content_block_id": "CB001",
                "type": "dialogue",
                "text": "I am back.",
                "speaker": None,
                "source_evidence_ids": [],
                "source_paragraph_ids": ["CH001_P001"],
            }
        ],
    }

    with pytest.raises(RuntimeError, match="dialogue block requires speaker"):
        _validate_script_scene_payload(payload, SceneStub(), {"CH001_P001"})


def test_invalid_block_type_is_rejected():
    payload = {
        "scene_id": "S001",
        "title": "Rainy Return",
        "content_blocks": [
            {
                "content_block_id": "CB001",
                "type": "not_a_real_type",
                "text": "She remembers the old letter.",
                "speaker": None,
                "source_evidence_ids": [],
                "source_paragraph_ids": ["CH001_P001"],
            }
        ],
    }

    with pytest.raises(RuntimeError, match="block type is invalid"):
        _validate_script_scene_payload(payload, SceneStub(), {"CH001_P001"})


def test_unknown_source_paragraph_is_rejected():
    payload = {
        "scene_id": "S001",
        "title": "Rainy Return",
        "content_blocks": [
            {
                "content_block_id": "CB001",
                "type": "action",
                "text": "She waits at the gate.",
                "speaker": None,
                "source_evidence_ids": [],
                "source_paragraph_ids": ["CH999_P001"],
            }
        ],
    }

    with pytest.raises(RuntimeError, match="unknown paragraphs"):
        _validate_script_scene_payload(payload, SceneStub(), {"CH001_P001"})
