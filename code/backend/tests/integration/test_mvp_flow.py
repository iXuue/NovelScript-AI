def test_mvp_flow_creates_project_uploads_confirms_scene_plan_and_exports(client):
    project = client.post("/projects", json={"name": "雨夜归来"}).json()
    project_id = project["project_id"]

    upload = client.post(
        f"/projects/{project_id}/uploads",
        files={"file": ("novel.md", "# 第一章 雨夜\n\n她回来了。\n\n# 第二章 旧信\n\n信封泛黄。")},
    )
    assert upload.status_code == 200

    chapters = client.get(f"/projects/{project_id}/chapters/pending").json()
    assert len(chapters["chapters"]) == 2

    confirm = client.post(
        f"/projects/{project_id}/chapters/confirm",
        json={"chapter_ids": [c["chapter_id"] for c in chapters["chapters"]]},
    )
    assert confirm.status_code == 200

    style = client.post(f"/projects/{project_id}/style-source", json={"kind": "builtin", "builtin_style": "suspense"})
    assert style.status_code == 200

    scene_plan = client.post(f"/projects/{project_id}/scene-plan/generate")
    assert scene_plan.status_code == 200

    confirm_scene_plan = client.post(f"/projects/{project_id}/scene-plan/confirm", json={"confirmation_source": "button"})
    assert confirm_scene_plan.status_code == 200

    script_run = client.post(f"/projects/{project_id}/scripts/generate")
    assert script_run.status_code == 200

    preview = client.get(f"/projects/{project_id}/scripts/current/yaml-preview")
    assert preview.status_code == 200
    assert "yaml" in preview.json()

    export = client.post(f"/projects/{project_id}/exports", json={"format": "yaml"})
    assert export.status_code == 200

