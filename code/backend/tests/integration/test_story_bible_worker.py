from app.core.database import get_db
from app.models.story import StoryBible


def test_scene_plan_generation_does_not_create_story_bible(client):
    project = client.post("/projects", json={"name": "Story bible bypass project"}).json()
    project_id = project["project_id"]
    upload = client.post(
        f"/projects/{project_id}/uploads",
        files={"file": ("novel.md", "# Chapter 1\n\nShe returns.\n\nThe door opens.")},
    )
    chapter_ids = [chapter["chapter_id"] for chapter in upload.json()["detected_chapters"]]
    assert client.post(f"/projects/{project_id}/chapters/confirm", json={"chapter_ids": chapter_ids}).status_code == 200
    assert client.post(f"/projects/{project_id}/style-source", json={"kind": "builtin", "builtin_style": "suspense"}).status_code == 200

    scene_plan = client.post(f"/projects/{project_id}/scene-plan/generate")

    assert scene_plan.status_code == 200
    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        assert db.query(StoryBible).filter(StoryBible.project_id == project_id).count() == 0
        task_types = [request.task_type for request in client.fake_llm_provider.requests]
        assert "story_bible" not in task_types
    finally:
        db.close()
