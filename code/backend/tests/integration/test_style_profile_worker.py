from app.core.database import get_db
from app.models.style import StyleProfile, StyleSourceRecord


def test_scene_plan_generation_parses_custom_text_style_profile_with_llm(client):
    project = client.post("/projects", json={"name": "Style project"}).json()
    project_id = project["project_id"]
    upload = client.post(
        f"/projects/{project_id}/uploads",
        files={"file": ("novel.md", "# Chapter 1\n\nShe returns.")},
    )
    chapter_ids = [chapter["chapter_id"] for chapter in upload.json()["detected_chapters"]]
    assert client.post(f"/projects/{project_id}/chapters/confirm", json={"chapter_ids": chapter_ids}).status_code == 200
    style = client.post(
        f"/projects/{project_id}/style-source",
        json={"kind": "custom_text", "style_text": "More suspense, short dialogue, fast rhythm."},
    )
    assert style.status_code == 200

    scene_plan = client.post(f"/projects/{project_id}/scene-plan/generate")

    assert scene_plan.status_code == 200
    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        source = db.query(StyleSourceRecord).filter(StyleSourceRecord.project_id == project_id).one()
        profile = db.query(StyleProfile).filter(StyleProfile.project_id == project_id).one()

        assert source.kind == "custom_text"
        assert "Suspense style" in profile.profile_text
        assert profile.source == "fake-analysis"
        assert "style_profile" in [request.task_type for request in client.fake_llm_provider.requests]
    finally:
        db.close()


def test_builtin_style_source_generates_default_style_profile_without_llm(client):
    project = client.post("/projects", json={"name": "Builtin style project"}).json()
    project_id = project["project_id"]
    upload = client.post(
        f"/projects/{project_id}/uploads",
        files={"file": ("novel.md", "# Chapter 1\n\nShe returns.")},
    )
    chapter_ids = [chapter["chapter_id"] for chapter in upload.json()["detected_chapters"]]
    assert client.post(f"/projects/{project_id}/chapters/confirm", json={"chapter_ids": chapter_ids}).status_code == 200
    style = client.post(f"/projects/{project_id}/style-source", json={"kind": "builtin", "builtin_style": "suspense"})
    assert style.status_code == 200

    scene_plan = client.post(f"/projects/{project_id}/scene-plan/generate")

    assert scene_plan.status_code == 200
    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        profile = db.query(StyleProfile).filter(StyleProfile.project_id == project_id).one()

        assert profile.profile_text
        assert profile.source == "builtin:suspense"
        assert "style_profile" not in [request.task_type for request in client.fake_llm_provider.requests]
    finally:
        db.close()
