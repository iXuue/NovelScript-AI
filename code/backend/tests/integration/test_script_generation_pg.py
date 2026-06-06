from app.core.database import get_db
from app.models.project import Project
from app.models.script import ScriptContentBlock, ScriptScene, ScriptSceneValidation, ScriptVersion


def _prepare_confirmed_scene_plan(client) -> str:
    project = client.post("/projects", json={"name": "Script project"}).json()
    project_id = project["project_id"]
    upload = client.post(
        f"/projects/{project_id}/uploads",
        files={"file": ("novel.md", "# Chapter 1\n\nShe returns.\n\nThe door opens.")},
    )
    assert upload.status_code == 200
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
    assert current.json()["scenes"][0]["characters"] == ["She"]
    assert current.json()["scenes"][0]["scene_purpose"] == "Establish the protagonist's return"
    assert current.json()["scenes"][0]["core_conflict"] == "Whether she enters the old house"
    assert current.json()["scenes"][0]["validation"]["passed"] is True
    assert current.json()["scenes"][0]["validation"]["source"] == "deterministic"
    assert current.json()["content_blocks"][0]["text"] == "She stands outside the old house gate."
    assert current.json()["content_blocks"][0]["source_evidence_ids"] == []
    assert current.json()["content_blocks"][0]["source_paragraph_ids"] == ["CH001_P001"]
    preview = client.get(f"/projects/{project_id}/scripts/current/yaml-preview")
    assert preview.status_code == 200
    assert "Rainy Return" in preview.json()["yaml"]

    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        project = db.get(Project, project_id)
        version = db.query(ScriptVersion).filter(ScriptVersion.project_id == project_id).one()
        scenes = db.query(ScriptScene).filter(ScriptScene.script_version_id == version.script_version_id).all()
        blocks = db.query(ScriptContentBlock).filter(ScriptContentBlock.script_version_id == version.script_version_id).all()
        validations = (
            db.query(ScriptSceneValidation)
            .filter(ScriptSceneValidation.script_version_id == version.script_version_id)
            .all()
        )

        assert project.stage == "script_ready"
        assert version.status == "current"
        assert len(scenes) == 1
        assert scenes[0].scene_id == "S001"
        assert scenes[0].characters == ["She"]
        assert scenes[0].scene_purpose == "Establish the protagonist's return"
        assert scenes[0].core_conflict == "Whether she enters the old house"
        assert len(blocks) == 2
        assert blocks[0].block_type == "action"
        assert blocks[1].block_type == "narration"
        assert blocks[0].source_evidence_ids == []
        assert blocks[0].source_paragraph_ids == ["CH001_P001"]
        assert len(validations) == 1
        assert validations[0].passed is True
        assert validations[0].issues == []
        assert validations[0].source == "deterministic"
    finally:
        db.close()


def test_script_generation_does_not_call_script_scene_validation_llm(client):
    project_id = _prepare_confirmed_scene_plan(client)

    generated = client.post(f"/projects/{project_id}/scripts/generate")

    assert generated.status_code == 200
    task_types = [request.task_type for request in client.fake_llm_provider.requests]
    assert "script_generation" in task_types
    assert "script_scene_validation" not in task_types
