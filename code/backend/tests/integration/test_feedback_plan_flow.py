from app.core.database import get_db
from app.models.feedback_plan_cache import FeedbackPlanCacheEntry
from app.models.scene_plan import ScenePlan
from app.models.script import ScriptVersion


def _prepare_project(client, chapters: int = 1) -> str:
    project = client.post("/projects", json={"name": "Feedback project"}).json()
    project_id = project["project_id"]
    if chapters == 1:
        text = "# Chapter 1\n\nShe returns.\n\nThe door opens."
    else:
        text = "# Chapter 1\n\nShe returns.\n\n# Chapter 2\n\nThe door opens."
    upload = client.post(f"/projects/{project_id}/uploads", files={"file": ("novel.md", text)})
    assert upload.status_code == 200
    chapter_ids = [chapter["chapter_id"] for chapter in upload.json()["detected_chapters"]]
    assert client.post(f"/projects/{project_id}/chapters/confirm", json={"chapter_ids": chapter_ids}).status_code == 200
    assert client.post(f"/projects/{project_id}/style-source", json={"kind": "builtin", "builtin_style": "suspense"}).status_code == 200
    assert client.post(f"/projects/{project_id}/scene-plan/generate").status_code == 200
    return project_id


def _prepare_script_project(client, chapters: int = 1) -> str:
    project_id = _prepare_project(client, chapters=chapters)
    assert client.post(f"/projects/{project_id}/scene-plan/confirm", json={"confirmation_source": "button"}).status_code == 200
    assert client.post(f"/projects/{project_id}/scripts/generate").status_code == 200
    return project_id


def test_scene_plan_feedback_uses_cache_and_waits_for_confirmation(client):
    project_id = _prepare_project(client)
    before = client.get(f"/projects/{project_id}/scene-plan").json()["scene_plan_id"]

    plan = client.post(
        f"/projects/{project_id}/conversations/primary/feedback-plan",
        json={"message": "Make the scene plan more tense.", "target": {"type": "scene_plan"}},
    )

    assert plan.status_code == 200
    assert plan.json()["cache_hit"] is False
    assert plan.json()["modification_plan"]["intent"] == "regenerate_scene_plan"
    assert client.get(f"/projects/{project_id}/scene-plan").json()["scene_plan_id"] == before
    feedback_prompt = [request.prompt for request in client.fake_llm_provider.requests if request.task_type == "feedback_plan"][-1]
    assert "She returns." not in feedback_prompt
    assert '"source_paragraph_ids"' in feedback_prompt

    cached = client.post(
        f"/projects/{project_id}/conversations/primary/feedback-plan",
        json={"message": "Make the scene plan more tense.", "target": {"type": "scene_plan"}},
    )

    assert cached.status_code == 200
    assert cached.json()["cache_hit"] is True
    assert cached.json()["feedback_plan_id"] == plan.json()["feedback_plan_id"]

    confirmed = client.post(
        f"/projects/{project_id}/conversations/primary/feedback-plan/{plan.json()['feedback_plan_id']}/confirm"
    )

    assert confirmed.status_code == 200
    current = client.get(f"/projects/{project_id}/scene-plan").json()
    assert current["scene_plan_id"] != before
    assert current["confirmed"] is False
    assert current["scenes"][0]["title"].startswith("Feedback ")

    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        assert db.query(FeedbackPlanCacheEntry).filter(FeedbackPlanCacheEntry.project_id == project_id).count() == 1
        assert db.query(ScenePlan).filter(ScenePlan.project_id == project_id).count() == 2
    finally:
        db.close()


def test_script_feedback_confirmation_regenerates_script_version(client):
    project_id = _prepare_script_project(client)
    before = client.get(f"/projects/{project_id}/scripts/current").json()

    plan = client.post(
        f"/projects/{project_id}/conversations/primary/feedback-plan",
        json={"message": "Make the screenplay less blunt.", "target": {"type": "script"}},
    )
    assert plan.status_code == 200
    assert plan.json()["modification_plan"]["intent"] == "regenerate_script"
    assert client.get(f"/projects/{project_id}/scripts/current").json()["script_version_id"] == before["script_version_id"]

    confirmed = client.post(
        f"/projects/{project_id}/conversations/primary/feedback-plan/{plan.json()['feedback_plan_id']}/confirm"
    )

    assert confirmed.status_code == 200
    current = client.get(f"/projects/{project_id}/scripts/current").json()
    assert current["script_version_id"] != before["script_version_id"]
    assert current["content_blocks"][0]["text"] == "Feedback revised scene from the confirmed plan."

    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        assert db.query(ScriptVersion).filter(ScriptVersion.project_id == project_id).count() == 2
    finally:
        db.close()


def test_scene_target_feedback_only_replaces_target_scene(client):
    project_id = _prepare_script_project(client, chapters=2)
    before = client.get(f"/projects/{project_id}/scripts/current").json()

    plan = client.post(
        f"/projects/{project_id}/conversations/primary/feedback-plan",
        json={"message": "Only revise the first scene.", "target": {"type": "scene", "scene_id": "S001"}},
    )
    assert plan.status_code == 200
    assert plan.json()["modification_plan"]["intent"] == "modify_scene"

    confirmed = client.post(
        f"/projects/{project_id}/conversations/primary/feedback-plan/{plan.json()['feedback_plan_id']}/confirm"
    )

    assert confirmed.status_code == 200
    current = client.get(f"/projects/{project_id}/scripts/current").json()
    before_by_scene = {block["scene_id"]: block["text"] for block in before["content_blocks"] if block["block_type"] == "action"}
    current_by_scene = {block["scene_id"]: block["text"] for block in current["content_blocks"] if block["block_type"] == "action"}
    assert current_by_scene["S001"] == "Feedback revised scene from the confirmed plan."
    assert current_by_scene["S002"] == before_by_scene["S002"]
