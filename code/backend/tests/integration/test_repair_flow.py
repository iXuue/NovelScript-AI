from app.core.database import get_db
from app.models.repair import RepairAttempt
from app.models.scene_plan import ScenePlan, ScenePlanValidation
from app.models.script import ScriptSceneValidation, ScriptVersion


def _prepare_project(client) -> str:
    project = client.post("/projects", json={"name": "Repair project"}).json()
    project_id = project["project_id"]
    upload = client.post(
        f"/projects/{project_id}/uploads",
        files={"file": ("novel.md", "# Chapter 1\n\nShe returns.\n\nThe door opens.")},
    )
    assert upload.status_code == 200
    chapter_ids = [chapter["chapter_id"] for chapter in upload.json()["detected_chapters"]]
    assert client.post(f"/projects/{project_id}/chapters/confirm", json={"chapter_ids": chapter_ids}).status_code == 200
    assert client.post(f"/projects/{project_id}/style-source", json={"kind": "builtin", "builtin_style": "suspense"}).status_code == 200
    return project_id


def _force_scene_plan_validation_failed(client, project_id: str) -> None:
    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        validation = (
            db.query(ScenePlanValidation)
            .join(ScenePlan, ScenePlan.scene_plan_id == ScenePlanValidation.scene_plan_id)
            .filter(ScenePlan.project_id == project_id, ScenePlan.is_current.is_(True))
            .one()
        )
        validation.passed = False
        validation.issues = [{"code": "manual_failure", "message": "Manual deterministic failure"}]
        db.commit()
    finally:
        db.close()


def _force_script_scene_validation_failed(client, project_id: str) -> None:
    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        version = db.query(ScriptVersion).filter(ScriptVersion.project_id == project_id, ScriptVersion.is_current.is_(True)).one()
        validation = (
            db.query(ScriptSceneValidation)
            .filter(ScriptSceneValidation.script_version_id == version.script_version_id, ScriptSceneValidation.scene_id == "S001")
            .one()
        )
        validation.passed = False
        validation.issues = [{"code": "manual_failure", "message": "Manual deterministic failure"}]
        version.status = "failed"
        db.commit()
    finally:
        db.close()


def test_scene_plan_repair_regenerates_failed_plan_and_revalidates(client):
    project_id = _prepare_project(client)
    assert client.post(f"/projects/{project_id}/scene-plan/generate").status_code == 200
    _force_scene_plan_validation_failed(client, project_id)
    assert client.post(f"/projects/{project_id}/scene-plan/confirm", json={"confirmation_source": "button"}).status_code == 409

    repaired = client.post(f"/projects/{project_id}/scene-plan/repair")

    assert repaired.status_code == 200
    assert repaired.json()["validation"]["passed"] is True
    assert repaired.json()["validation"]["source"] == "deterministic"
    assert repaired.json()["scenes"][0]["source_evidence_ids"] == []
    assert repaired.json()["scenes"][0]["source_paragraph_ids"] == ["CH001_P001"]
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
    project_id = _prepare_project(client)
    assert client.post(f"/projects/{project_id}/scene-plan/generate").status_code == 200

    _force_scene_plan_validation_failed(client, project_id)
    assert client.post(f"/projects/{project_id}/scene-plan/repair").status_code == 200
    _force_scene_plan_validation_failed(client, project_id)
    assert client.post(f"/projects/{project_id}/scene-plan/repair").status_code == 200
    _force_scene_plan_validation_failed(client, project_id)
    third = client.post(f"/projects/{project_id}/scene-plan/repair")

    assert third.status_code == 409
    assert third.json()["error"]["code"] == "repair_attempts_exceeded"


def test_script_scene_repair_uses_paragraph_sources_and_revalidates(client):
    project_id = _prepare_project(client)
    assert client.post(f"/projects/{project_id}/scene-plan/generate").status_code == 200
    assert client.post(f"/projects/{project_id}/scene-plan/confirm", json={"confirmation_source": "button"}).status_code == 200
    assert client.post(f"/projects/{project_id}/scripts/generate").status_code == 200
    _force_script_scene_validation_failed(client, project_id)

    repaired = client.post(f"/projects/{project_id}/scripts/scenes/S001/repair")

    assert repaired.status_code == 200
    assert repaired.json()["scene_id"] == "S001"
    assert repaired.json()["validation"]["passed"] is True
    current = client.get(f"/projects/{project_id}/scripts/current")
    assert current.status_code == 200
    assert current.json()["status"] == "current"
    assert current.json()["scenes"][0]["validation"]["passed"] is True
    assert current.json()["content_blocks"][0]["source_paragraph_ids"] == ["CH001_P001"]
    assert current.json()["content_blocks"][0]["source_evidence_ids"] == []

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
        assert validation.source == "deterministic"
        assert len(attempts) == 1
        assert attempts[0].artifact_type == "script_scene"
        assert attempts[0].status == "success"
    finally:
        db.close()


def test_script_scene_repair_is_limited_to_two_attempts(client):
    project_id = _prepare_project(client)
    assert client.post(f"/projects/{project_id}/scene-plan/generate").status_code == 200
    assert client.post(f"/projects/{project_id}/scene-plan/confirm", json={"confirmation_source": "button"}).status_code == 200
    assert client.post(f"/projects/{project_id}/scripts/generate").status_code == 200

    _force_script_scene_validation_failed(client, project_id)
    assert client.post(f"/projects/{project_id}/scripts/scenes/S001/repair").status_code == 200
    _force_script_scene_validation_failed(client, project_id)
    assert client.post(f"/projects/{project_id}/scripts/scenes/S001/repair").status_code == 200
    _force_script_scene_validation_failed(client, project_id)
    third = client.post(f"/projects/{project_id}/scripts/scenes/S001/repair")

    assert third.status_code == 409
    assert third.json()["error"]["code"] == "repair_attempts_exceeded"
