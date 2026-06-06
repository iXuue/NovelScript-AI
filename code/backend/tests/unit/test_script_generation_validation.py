import pytest

from app.domain.artifacts import ArtifactStatus
from app.models.script import ScriptContentBlock, ScriptScene, ScriptVersion
from app.services.store import now_utc
from app.services.script_service import _validate_script_scene_payload
from app.services.script_service import _replace_script_scene_content


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
        title="旧场景",
        source_chapter_ids=["CH001"],
        scene_info="旧信息",
        characters=[],
        scene_purpose="旧目的",
        core_conflict="旧冲突",
        created_at=timestamp,
        updated_at=timestamp,
    )
    later_scene = ScriptScene(
        script_version_id=version.script_version_id,
        project_id=version.project_id,
        scene_id="S002",
        order=2,
        title="后续场景",
        source_chapter_ids=["CH002"],
        scene_info="后续信息",
        characters=[],
        scene_purpose="后续目的",
        core_conflict="后续冲突",
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
            text=f"旧块 {index}",
            speaker=None,
            source_evidence_ids=[],
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
            text="后续场景块",
            speaker=None,
            source_evidence_ids=[],
            created_at=timestamp,
            updated_at=timestamp,
        )
    ]
    test_db.add(version)
    test_db.commit()

    repaired_scene = {
        "title": "修复场景",
        "source_chapter_ids": ["CH001"],
        "scene_info": "新信息",
        "characters": [],
        "scene_purpose": "新目的",
        "core_conflict": "新冲突",
        "content_blocks": [
            {
                "content_block_id": f"CB{index:03d}",
                "type": "action",
                "text": f"新块 {index}",
                "speaker": None,
                "source_evidence_ids": [],
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
