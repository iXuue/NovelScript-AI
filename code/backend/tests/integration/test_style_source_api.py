def test_style_reference_upload_does_not_replace_novel_upload(client):
    project = client.post("/projects", json={"name": "雨夜归来"}).json()
    project_id = project["project_id"]

    novel = client.post(
        f"/projects/{project_id}/uploads",
        files={"file": ("novel.md", "# 第一章\n\n她回来了。")},
    )
    assert novel.status_code == 200

    style_file = client.post(
        f"/projects/{project_id}/style-reference-uploads",
        files={"file": ("past-script.md", "# 场景一\n\n她：我回来了。")},
    )
    assert style_file.status_code == 200
    assert style_file.json()["purpose"] == "style_reference"

    chapters = client.get(f"/projects/{project_id}/chapters/pending").json()
    assert len(chapters["chapters"]) == 1

