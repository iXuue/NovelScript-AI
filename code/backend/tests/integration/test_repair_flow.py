from app.core.database import get_db
from app.models.repair import RepairAttempt
from app.models.script import ScriptSceneValidation, ScriptVersion


def _prepare_project(client) -> str:
    project = client.post("/projects", json={"name": "修复项目"}).json()
    project_id = project["project_id"]
    upload = client.post(
        f"/projects/{project_id}/uploads",
        files={"file": ("novel.md", "# 第一章 雨夜\n\n她回来了。\n\n门开了。")},
    )
    chapter_ids = [chapter["chapter_id"] for chapter in upload.json()["detected_chapters"]]
    assert client.post(f"/projects/{project_id}/chapters/confirm", json={"chapter_ids": chapter_ids}).status_code == 200
    assert client.post(f"/projects/{project_id}/style-source", json={"kind": "builtin", "builtin_style": "suspense"}).status_code == 200
    return project_id


def test_scene_plan_repair_replaces_failed_plan_and_revalidates(client):
    client.fake_llm_provider.fail_scene_plan_validation = True
    project_id = _prepare_project(client)
    assert client.post(f"/projects/{project_id}/scene-plan/generate").status_code == 200
    assert client.post(f"/projects/{project_id}/scene-plan/confirm", json={"confirmation_source": "button"}).status_code == 409

    client.fake_llm_provider.fail_scene_plan_validation = False
    repaired = client.post(f"/projects/{project_id}/scene-plan/repair")

    assert repaired.status_code == 200
    assert repaired.json()["validation"]["passed"] is True
    assert repaired.json()["scenes"][0]["title"] == "雨夜归来"
    assert client.post(f"/projects/{project_id}/scene-plan/confirm", json={"confirmation_source": "button"}).status_code == 200

    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        attempts = db.query(RepairAttempt).filter(RepairAttempt.project_id == project_id).all()
        assert len(attempts) == 1
        assert attempts[0].artifact_type == "scene_plan"
        assert attempts[0].status == "success"
    finally:
        db.close()


def test_scene_plan_repair_is_limited_to_two_attempts(client):
    client.fake_llm_provider.fail_scene_plan_validation = True
    project_id = _prepare_project(client)
    assert client.post(f"/projects/{project_id}/scene-plan/generate").status_code == 200

    assert client.post(f"/projects/{project_id}/scene-plan/repair").status_code == 200
    assert client.post(f"/projects/{project_id}/scene-plan/repair").status_code == 200
    third = client.post(f"/projects/{project_id}/scene-plan/repair")

    assert third.status_code == 409
    assert third.json()["error"]["code"] == "repair_attempts_exceeded"


def test_script_scene_repair_replaces_failed_scene_blocks_and_revalidates(client):
    project_id = _prepare_project(client)
    assert client.post(f"/projects/{project_id}/scene-plan/generate").status_code == 200
    assert client.post(f"/projects/{project_id}/scene-plan/confirm", json={"confirmation_source": "button"}).status_code == 200
    client.fake_llm_provider.fail_script_scene_validation = True
    assert client.post(f"/projects/{project_id}/scripts/generate").status_code == 409

    client.fake_llm_provider.fail_script_scene_validation = False
    repaired = client.post(f"/projects/{project_id}/scripts/scenes/S001/repair")

    assert repaired.status_code == 200
    assert repaired.json()["scene_id"] == "S001"
    assert repaired.json()["validation"]["passed"] is True
    current = client.get(f"/projects/{project_id}/scripts/current")
    assert current.status_code == 200
    assert current.json()["status"] == "current"
    assert current.json()["scenes"][0]["validation"]["passed"] is True

    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        version = db.query(ScriptVersion).filter(ScriptVersion.project_id == project_id).one()
        validation = (
            db.query(ScriptSceneValidation)
            .filter(ScriptSceneValidation.script_version_id == version.script_version_id, ScriptSceneValidation.scene_id == "S001")
            .one()
        )
        attempts = db.query(RepairAttempt).filter(RepairAttempt.project_id == project_id).all()
        assert version.status == "current"
        assert validation.passed is True
        assert len(attempts) == 1
        assert attempts[0].artifact_type == "script_scene"
        assert attempts[0].status == "success"
    finally:
        db.close()


def test_script_scene_repair_is_limited_to_two_attempts(client):
    project_id = _prepare_project(client)
    assert client.post(f"/projects/{project_id}/scene-plan/generate").status_code == 200
    assert client.post(f"/projects/{project_id}/scene-plan/confirm", json={"confirmation_source": "button"}).status_code == 200
    client.fake_llm_provider.fail_script_scene_validation = True
    assert client.post(f"/projects/{project_id}/scripts/generate").status_code == 409

    assert client.post(f"/projects/{project_id}/scripts/scenes/S001/repair").status_code == 200
    assert client.post(f"/projects/{project_id}/scripts/scenes/S001/repair").status_code == 200
    third = client.post(f"/projects/{project_id}/scripts/scenes/S001/repair")

    assert third.status_code == 409
    assert third.json()["error"]["code"] == "repair_attempts_exceeded"
