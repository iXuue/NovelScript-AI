from app.core.database import get_db
from app.models.script import ScriptContentBlock, ScriptScene, ScriptVersion


def test_script_generation_writes_each_confirmed_scene_to_pg(client):
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

    generated = client.post(f"/projects/{project_id}/scripts/generate")

    assert generated.status_code == 200
    current = client.get(f"/projects/{project_id}/scripts/current")
    assert current.status_code == 200
    assert current.json()["scenes"][0]["scene_id"] == "S001"
    assert current.json()["scenes"][0]["characters"] == ["她"]
    assert current.json()["scenes"][0]["scene_purpose"] == "建立人物回归"
    assert current.json()["scenes"][0]["core_conflict"] == "她是否进入旧宅"
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
    finally:
        db.close()
