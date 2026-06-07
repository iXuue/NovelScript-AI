import pytest

from app.domain.artifacts import ArtifactStatus
from app.models.script import ScriptContentBlock, ScriptScene, ScriptVersion
from app.services.script_service import _replace_script_scene_content, _validate_script_scene_payload
from app.services.source_id_service import normalize_paragraph_id
from app.services.store import now_utc


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


def test_empty_source_paragraph_error_includes_block_id():
    payload = {
        "scene_id": "S001",
        "title": "Rainy Return",
        "content_blocks": [
            {
                "content_block_id": "CB009",
                "type": "action",
                "text": "She waits at the gate.",
                "speaker": None,
                "source_evidence_ids": [],
                "source_paragraph_ids": [],
            }
        ],
    }

    with pytest.raises(RuntimeError, match="CB009 source_paragraph_ids must be non-empty"):
        _validate_script_scene_payload(payload, SceneStub(), {"CH001_P001"})


def test_source_paragraph_ids_are_normalized_when_known():
    scene = SceneStub()
    scene.source_paragraph_ids = ["CH001_P011", "CH002_P003"]
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
                "source_paragraph_ids": ["CH001_P11", "CH2_P3"],
            }
        ],
    }

    validated = _validate_script_scene_payload(payload, scene, {"CH001_P011", "CH002_P003"})

    assert validated["content_blocks"][0]["source_paragraph_ids"] == ["CH001_P011", "CH002_P003"]


def test_source_paragraph_id_normalization_keeps_unknown_values_rejectable():
    assert normalize_paragraph_id("CH999_P1", {"CH001_P001"}) == "CH999_P1"
    assert normalize_paragraph_id("BAD_ID", {"CH001_P001"}) == "BAD_ID"


def test_repair_scene_reassigns_block_ids_that_collide_with_later_scenes(test_db):
    timestamp = now_utc()
    version = ScriptVersion(
        script_version_id="script_v_test",
        project_id="proj_test",
        status=ArtifactStatus.failed,
        source="test",
        generated_at=timestamp,
        created_at=timestamp,
        updated_at=timestamp,
    )
    scene = ScriptScene(
        script_version_id=version.script_version_id,
        project_id=version.project_id,
        scene_id="S001",
        order=1,
        title="Old scene",
        source_chapter_ids=["CH001"],
        scene_info="Old info",
        characters=[],
        scene_purpose="Old purpose",
        core_conflict="Old conflict",
        created_at=timestamp,
        updated_at=timestamp,
    )
    later_scene = ScriptScene(
        script_version_id=version.script_version_id,
        project_id=version.project_id,
        scene_id="S002",
        order=2,
        title="Later scene",
        source_chapter_ids=["CH002"],
        scene_info="Later info",
        characters=[],
        scene_purpose="Later purpose",
        core_conflict="Later conflict",
        created_at=timestamp,
        updated_at=timestamp,
    )
    version.scenes = [scene, later_scene]
    version.content_blocks = [
        ScriptContentBlock(
            script_version_id=version.script_version_id,
            project_id=version.project_id,
            scene_id="S001",
            content_block_id=f"CB{index:03d}",
            order=index,
            block_type="action",
            text=f"Old block {index}",
            speaker=None,
            source_evidence_ids=[],
            source_paragraph_ids=["CH001_P001"],
            created_at=timestamp,
            updated_at=timestamp,
        )
        for index in range(1, 10)
    ] + [
        ScriptContentBlock(
            script_version_id=version.script_version_id,
            project_id=version.project_id,
            scene_id="S002",
            content_block_id="CB010",
            order=1,
            block_type="action",
            text="Later scene block",
            speaker=None,
            source_evidence_ids=[],
            source_paragraph_ids=["CH002_P001"],
            created_at=timestamp,
            updated_at=timestamp,
        )
    ]
    test_db.add(version)
    test_db.commit()

    repaired_scene = {
        "title": "Repaired scene",
        "source_chapter_ids": ["CH001"],
        "source_paragraph_ids": ["CH001_P001"],
        "scene_info": "New info",
        "characters": [],
        "scene_purpose": "New purpose",
        "core_conflict": "New conflict",
        "content_blocks": [
            {
                "content_block_id": f"CB{index:03d}",
                "type": "action",
                "text": f"New block {index}",
                "speaker": None,
                "source_evidence_ids": [],
                "source_paragraph_ids": ["CH001_P001"],
            }
            for index in range(1, 11)
        ],
    }

    _replace_script_scene_content(test_db, version, scene, repaired_scene)
    test_db.commit()

    block_ids = [
        block.content_block_id
        for block in test_db.query(ScriptContentBlock)
        .filter(ScriptContentBlock.script_version_id == version.script_version_id)
        .order_by(ScriptContentBlock.content_block_id)
        .all()
    ]
    assert len(block_ids) == len(set(block_ids))
    assert "CB010" in [
        block.content_block_id
        for block in test_db.query(ScriptContentBlock).filter(ScriptContentBlock.scene_id == "S002").all()
    ]
