from app.core.database import get_db
from app.models.chapter import Chapter, Paragraph
from app.models.checkpoint import Checkpoint
from app.models.project import Project
from app.services.store import STORE


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


def test_upload_persists_detected_chapters_and_paragraphs_to_database(client):
    project = client.post("/projects", json={"name": "落库项目"}).json()
    project_id = project["project_id"]

    upload = client.post(
        f"/projects/{project_id}/uploads",
        files={"file": ("novel.md", "# 第一章 雨夜\n\n她回来了。\n\n门开了。")},
    )

    assert upload.status_code == 200
    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        chapters = db.query(Chapter).filter(Chapter.project_id == project_id).all()
        paragraphs = db.query(Paragraph).filter(Paragraph.project_id == project_id).all()

        assert [chapter.chapter_id for chapter in chapters] == ["CH001"]
        assert [paragraph.paragraph_id for paragraph in paragraphs] == ["CH001_P001", "CH001_P002"]
        assert [paragraph.text for paragraph in paragraphs] == ["她回来了。", "门开了。"]
    finally:
        db.close()


def test_pending_and_confirm_chapters_use_postgres_not_store(client):
    project = client.post("/projects", json={"name": "确认项目"}).json()
    project_id = project["project_id"]
    upload = client.post(
        f"/projects/{project_id}/uploads",
        files={"file": ("novel.md", "# 第一章 雨夜\n\n她回来了。\n\n# 第二章 旧信\n\n信来了。")},
    )
    assert upload.status_code == 200

    STORE.chapters_pending.clear()
    pending = client.get(f"/projects/{project_id}/chapters/pending")

    assert pending.status_code == 200
    chapter_ids = [chapter["chapter_id"] for chapter in pending.json()["chapters"]]
    assert chapter_ids == ["CH001", "CH002"]

    confirm = client.post(f"/projects/{project_id}/chapters/confirm", json={"chapter_ids": chapter_ids})

    assert confirm.status_code == 200
    assert confirm.json()["stage"] == "chapters_confirmed"
    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        chapters = db.query(Chapter).filter(Chapter.project_id == project_id).order_by(Chapter.order).all()
        checkpoint = db.get(Checkpoint, confirm.json()["checkpoint_id"])
        saved_project = db.get(Project, project_id)

        assert [chapter.status for chapter in chapters] == ["confirmed", "confirmed"]
        assert saved_project.stage == "chapters_confirmed"
        assert checkpoint is not None
        assert checkpoint.project_id == project_id
        assert checkpoint.stage == "chapters_confirmed"
    finally:
        db.close()
