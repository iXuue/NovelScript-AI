from app.core.database import get_db
from app.models.project import Project
from app.models.script import ScriptContentBlock, ScriptScene, ScriptSceneValidation, ScriptVersion


def _prepare_confirmed_scene_plan(client) -> str:
    project = client.post("/projects", json={"name": "逐场剧本项目"}).json()
    project_id = project["project_id"]
    upload = client.post(
        f"/projects/{project_id}/uploads",
        files={"file": ("novel.md", "# 第一章 雨夜\n\n她回来了。\n\n门开了。")},
    )
    chapter_ids = [chapter["chapter_id"] for chapter in upload.json()["detected_chapters"]]
    assert client.post(f"/projects/{project_id}/chapters/confirm", json={"chapter_ids": chapter_ids}).status_code == 200
    assert client.post(f"/projects/{project_id}/style-source", json={"kind": "builtin", "builtin_style": "suspense"}).status_code == 200
    assert client.post(f"/projects/{project_id}/scene-plan/generate").status_code == 200
    assert client.post(f"/projects/{project_id}/scene-plan/confirm", json={"confirmation_source": "button"}).status_code == 200
    return project_id


def test_script_generation_writes_each_confirmed_scene_and_validation_to_pg(client):
    project_id = _prepare_confirmed_scene_plan(client)

    generated = client.post(f"/projects/{project_id}/scripts/generate")

    assert generated.status_code == 200
    current = client.get(f"/projects/{project_id}/scripts/current")
    assert current.status_code == 200
    assert current.json()["scenes"][0]["scene_id"] == "S001"
    assert current.json()["scenes"][0]["characters"] == ["她"]
    assert current.json()["scenes"][0]["scene_purpose"] == "建立人物回归"
    assert current.json()["scenes"][0]["core_conflict"] == "她是否进入旧宅"
    assert current.json()["scenes"][0]["validation"]["passed"] is True
    assert current.json()["content_blocks"][0]["text"] == "她站在旧宅门口。"
    preview = client.get(f"/projects/{project_id}/scripts/current/yaml-preview")
    assert preview.status_code == 200
    assert "雨夜归来" in preview.json()["yaml"]

    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        version = db.query(ScriptVersion).filter(ScriptVersion.project_id == project_id).one()
        scenes = db.query(ScriptScene).filter(ScriptScene.script_version_id == version.script_version_id).all()
        blocks = db.query(ScriptContentBlock).filter(ScriptContentBlock.script_version_id == version.script_version_id).all()
        validations = (
            db.query(ScriptSceneValidation)
            .filter(ScriptSceneValidation.script_version_id == version.script_version_id)
            .all()
        )

        assert version.status == "current"
        assert len(scenes) == 1
        assert scenes[0].scene_id == "S001"
        assert scenes[0].characters == ["她"]
        assert scenes[0].scene_purpose == "建立人物回归"
        assert scenes[0].core_conflict == "她是否进入旧宅"
        assert len(blocks) == 2
        assert blocks[0].block_type == "action"
        assert blocks[1].block_type == "narration"
        assert blocks[0].source_evidence_ids == ["EV001"]
        assert len(validations) == 1
        assert validations[0].passed is True
        assert validations[0].issues == []
    finally:
        db.close()


def test_script_generation_returns_409_when_any_scene_validation_fails(client):
    client.fake_llm_provider.fail_script_scene_validation = True
    project_id = _prepare_confirmed_scene_plan(client)

    generated = client.post(f"/projects/{project_id}/scripts/generate")

    assert generated.status_code == 409
    assert generated.json()["error"]["code"] == "script_scene_validation_failed"
    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        project = db.get(Project, project_id)
        version = db.query(ScriptVersion).filter(ScriptVersion.project_id == project_id).one()
        validation = (
            db.query(ScriptSceneValidation)
            .filter(ScriptSceneValidation.script_version_id == version.script_version_id)
            .one()
        )

        assert project.stage == "script_generating"
        assert version.status == "failed"
        assert validation.passed is False
    finally:
        db.close()
