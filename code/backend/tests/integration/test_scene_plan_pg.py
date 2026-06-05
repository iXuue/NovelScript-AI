from app.core.database import get_db
from app.models.checkpoint import Checkpoint
from app.models.scene_plan import ScenePlan, ScenePlanScene, ScenePlanValidation


def test_scene_plan_generate_get_validate_and_confirm_are_pg_backed(client):
    project = client.post("/projects", json={"name": "场景规划项目"}).json()
    project_id = project["project_id"]
    upload = client.post(
        f"/projects/{project_id}/uploads",
        files={"file": ("novel.md", "# 第一章 雨夜\n\n她回来了。\n\n门开了。")},
    )
    chapter_ids = [chapter["chapter_id"] for chapter in upload.json()["detected_chapters"]]
    assert client.post(f"/projects/{project_id}/chapters/confirm", json={"chapter_ids": chapter_ids}).status_code == 200
    assert client.post(f"/projects/{project_id}/style-source", json={"kind": "builtin", "builtin_style": "suspense"}).status_code == 200

    generated = client.post(f"/projects/{project_id}/scene-plan/generate")

    assert generated.status_code == 200
    scene_plan_id = generated.json()["scene_plan_id"]
    fetched = client.get(f"/projects/{project_id}/scene-plan")
    assert fetched.status_code == 200
    assert fetched.json()["scene_plan_id"] == scene_plan_id
    assert fetched.json()["confirmed"] is False
    assert fetched.json()["validation"]["passed"] is True
    assert fetched.json()["validation"]["issues"] == []
    assert fetched.json()["scenes"][0]["source_chapter_ids"] == ["CH001"]
    assert fetched.json()["scenes"][0]["source_evidence_ids"] == ["EV001"]
    assert fetched.json()["scenes"][0]["interior_exterior"] == "外景"
    assert fetched.json()["scenes"][0]["must_cover_plot"] == ["她在雨夜回到旧宅"]
    assert fetched.json()["scenes"][0]["must_keep_dialogue"] == ["她回来了。"]
    assert fetched.json()["scenes"][0]["must_keep_visual_elements"] == ["雨夜", "旧宅门口"]
    assert fetched.json()["scenes"][0]["must_keep_foreshadowing"] == ["旧信"]

    confirm = client.post(f"/projects/{project_id}/scene-plan/confirm", json={"confirmation_source": "button"})

    assert confirm.status_code == 200
    assert confirm.json()["confirmed"] is True
    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        plan = db.query(ScenePlan).filter(ScenePlan.project_id == project_id).one()
        scenes = db.query(ScenePlanScene).filter(ScenePlanScene.scene_plan_id == scene_plan_id).all()
        validation = db.query(ScenePlanValidation).filter(ScenePlanValidation.scene_plan_id == scene_plan_id).one()
        checkpoint = db.get(Checkpoint, confirm.json()["checkpoint_id"])

        assert plan.confirmed is True
        assert len(scenes) == 1
        assert scenes[0].interior_exterior == "外景"
        assert scenes[0].must_cover_plot == ["她在雨夜回到旧宅"]
        assert scenes[0].must_keep_dialogue == ["她回来了。"]
        assert scenes[0].must_keep_visual_elements == ["雨夜", "旧宅门口"]
        assert scenes[0].must_keep_foreshadowing == ["旧信"]
        assert validation.passed is True
        assert validation.issues == []
        assert checkpoint is not None
        assert checkpoint.stage == "scene_plan_confirmed"
    finally:
        db.close()


def test_scene_plan_confirmation_requires_passed_validation(client):
    client.fake_llm_provider.fail_scene_plan_validation = True
    project = client.post("/projects", json={"name": "校验失败项目"}).json()
    project_id = project["project_id"]
    upload = client.post(
        f"/projects/{project_id}/uploads",
        files={"file": ("novel.md", "# 第一章 雨夜\n\n她回来了。")},
    )
    chapter_ids = [chapter["chapter_id"] for chapter in upload.json()["detected_chapters"]]
    assert client.post(f"/projects/{project_id}/chapters/confirm", json={"chapter_ids": chapter_ids}).status_code == 200
    assert client.post(f"/projects/{project_id}/style-source", json={"kind": "builtin", "builtin_style": "suspense"}).status_code == 200
    assert client.post(f"/projects/{project_id}/scene-plan/generate").status_code == 200

    confirm = client.post(f"/projects/{project_id}/scene-plan/confirm", json={"confirmation_source": "button"})

    assert confirm.status_code == 409
    assert confirm.json()["error"]["code"] == "scene_plan_validation_failed"
