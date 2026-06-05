def test_upload_accepts_multiple_novel_files_and_detects_chapters_in_natural_order(client):
    project = client.post("/projects", json={"name": "多文档项目"}).json()
    project_id = project["project_id"]

    upload = client.post(
        f"/projects/{project_id}/uploads",
        files=[
            ("files", ("chapter10.txt", "第十章 终局\n\n雨停了。")),
            ("files", ("chapter2.txt", "她推开门。\n\n屋里没人。")),
            ("files", ("chapter1.txt", "第一章 雨夜\n\n她回来了。")),
        ],
    )

    assert upload.status_code == 200
    assert [chapter["chapter_id"] for chapter in upload.json()["detected_chapters"]] == [
        "CH001",
        "CH002",
        "CH003",
    ]
    assert [chapter["title"] for chapter in upload.json()["detected_chapters"]] == [
        "第一章 雨夜",
        "chapter2",
        "第十章 终局",
    ]

