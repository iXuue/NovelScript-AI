from app.core.database import get_db
from app.models.analysis import EvidenceItem
from app.models.checkpoint import Checkpoint
from app.models.scene_plan import ScenePlan, ScenePlanScene, ScenePlanValidation
from app.models.story import StoryBible


def _prepare_project(client) -> str:
    project = client.post("/projects", json={"name": "Scene plan project"}).json()
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


def test_scene_plan_generate_get_validate_and_confirm_are_pg_backed(client):
    project_id = _prepare_project(client)

    generated = client.post(f"/projects/{project_id}/scene-plan/generate")

    assert generated.status_code == 200
    scene_plan_id = generated.json()["scene_plan_id"]
    fetched = client.get(f"/projects/{project_id}/scene-plan")
    assert fetched.status_code == 200
    scene = fetched.json()["scenes"][0]
    assert fetched.json()["scene_plan_id"] == scene_plan_id
    assert fetched.json()["confirmed"] is False
    assert fetched.json()["validation"]["passed"] is True
    assert fetched.json()["validation"]["source"] == "deterministic"
    assert scene["source_chapter_ids"] == ["CH001"]
    assert scene["source_evidence_ids"] == []
    assert scene["source_paragraph_ids"] == ["CH001_P001"]

    confirm = client.post(f"/projects/{project_id}/scene-plan/confirm", json={"confirmation_source": "button"})

    assert confirm.status_code == 200
    assert confirm.json()["confirmed"] is True
    task_types = [request.task_type for request in client.fake_llm_provider.requests]
    assert "scene_plan_chapter" in task_types
    assert "evidence_extraction" not in task_types
    assert "story_bible" not in task_types
    assert "scene_plan_validation" not in task_types

    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        plan = db.query(ScenePlan).filter(ScenePlan.project_id == project_id).one()
        scenes = db.query(ScenePlanScene).filter(ScenePlanScene.scene_plan_id == scene_plan_id).all()
        validation = db.query(ScenePlanValidation).filter(ScenePlanValidation.scene_plan_id == scene_plan_id).one()
        checkpoint = db.get(Checkpoint, confirm.json()["checkpoint_id"])

        assert plan.confirmed is True
        assert len(scenes) == 1
        assert scenes[0].source_evidence_ids == []
        assert scenes[0].source_paragraph_ids == ["CH001_P001"]
        assert validation.passed is True
        assert validation.source == "deterministic"
        assert db.query(EvidenceItem).filter(EvidenceItem.project_id == project_id).count() == 0
        assert db.query(StoryBible).filter(StoryBible.project_id == project_id).count() == 0
        assert checkpoint is not None
        assert checkpoint.stage == "scene_plan_confirmed"
    finally:
        db.close()


def test_scene_plan_confirmation_requires_passed_validation(client):
    project_id = _prepare_project(client)
    assert client.post(f"/projects/{project_id}/scene-plan/generate").status_code == 200

    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        validation = (
            db.query(ScenePlanValidation)
            .join(ScenePlan, ScenePlan.scene_plan_id == ScenePlanValidation.scene_plan_id)
            .filter(ScenePlan.project_id == project_id)
            .one()
        )
        validation.passed = False
        validation.issues = [{"code": "manual_failure", "message": "Manual deterministic failure"}]
        db.commit()
    finally:
        db.close()

    confirm = client.post(f"/projects/{project_id}/scene-plan/confirm", json={"confirmation_source": "button"})

    assert confirm.status_code == 409
    assert confirm.json()["error"]["code"] == "scene_plan_validation_failed"


def test_scene_plan_generation_runtime_failure_returns_api_error(client):
    project_id = _prepare_project(client)
    client.fake_llm_provider.fail_next_request = True

    generated = client.post(f"/projects/{project_id}/scene-plan/generate")

    assert generated.status_code == 502
    assert generated.json()["error"]["code"] == "scene_plan_generation_failed"
    assert generated.json()["error"]["details"]["reason"] == "fake LLM failure"
