from app.core.database import get_db
from app.models.story import StoryBible


def test_scene_plan_generation_creates_story_bible_from_summaries_and_evidence(client):
    project = client.post("/projects", json={"name": "故事圣经项目"}).json()
    project_id = project["project_id"]
    upload = client.post(
        f"/projects/{project_id}/uploads",
        files={"file": ("novel.md", "# 第一章 雨夜\n\n她回来了。\n\n门开了。")},
    )
    chapter_ids = [chapter["chapter_id"] for chapter in upload.json()["detected_chapters"]]
    assert client.post(f"/projects/{project_id}/chapters/confirm", json={"chapter_ids": chapter_ids}).status_code == 200
    assert client.post(f"/projects/{project_id}/style-source", json={"kind": "builtin", "builtin_style": "suspense"}).status_code == 200

    scene_plan = client.post(f"/projects/{project_id}/scene-plan/generate")

    assert scene_plan.status_code == 200
    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        story_bible = db.query(StoryBible).filter(StoryBible.project_id == project_id).one()

        assert story_bible.title == "雨夜归来"
        assert story_bible.logline
        assert story_bible.main_characters
        assert story_bible.timeline
        assert story_bible.source == "fake-analysis"
        assert "story_bible" in [request.task_type for request in client.fake_llm_provider.requests]
    finally:
        db.close()
