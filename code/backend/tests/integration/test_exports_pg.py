from app.core.database import get_db
from app.models.export import ExportJob
from app.services.store import STORE


def _prepare_script(client) -> str:
    project = client.post("/projects", json={"name": "导出项目"}).json()
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
    assert client.post(f"/projects/{project_id}/scripts/generate").status_code == 200
    STORE.scripts.clear()
    STORE.exports.clear()
    return project_id


def test_export_uses_pg_script_and_downloads_yaml_content_for_requested_file_format(client):
    project_id = _prepare_script(client)

    created = client.post(f"/projects/{project_id}/exports", json={"format": "pdf"})

    assert created.status_code == 200
    export_id = created.json()["export_id"]
    assert created.json()["format"] == "pdf"
    assert created.json()["filename"].endswith(".pdf")
    downloaded = client.get(f"/projects/{project_id}/exports/{export_id}")
    assert downloaded.status_code == 200
    assert "attachment" in downloaded.headers["content-disposition"]
    assert 'filename="script.pdf"' in downloaded.headers["content-disposition"]
    assert "雨夜归来" in downloaded.text
    assert "content_block_id" not in downloaded.text
    assert "source_evidence_ids" not in downloaded.text

    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        export = db.query(ExportJob).filter(ExportJob.export_id == export_id).one()
        assert export.project_id == project_id
        assert export.format == "pdf"
        assert export.status == "succeeded"
        assert export.filename == "script.pdf"
    finally:
        db.close()


def test_export_formats_share_yaml_body_but_use_different_extensions(client):
    project_id = _prepare_script(client)
    bodies = {}
    filenames = {}

    for export_format in ["yaml", "txt", "markdown", "docx"]:
        created = client.post(f"/projects/{project_id}/exports", json={"format": export_format})
        assert created.status_code == 200
        filenames[export_format] = created.json()["filename"]
        bodies[export_format] = client.get(created.json()["download_url"]).text

    assert filenames == {
        "yaml": "script.yaml",
        "txt": "script.txt",
        "markdown": "script.md",
        "docx": "script.docx",
    }
    assert len(set(bodies.values())) == 1


def test_export_clean_json_produces_json_without_internal_fields(client):
    project_id = _prepare_script(client)

    created = client.post(f"/projects/{project_id}/exports", json={"format": "clean_json"})

    assert created.status_code == 200
    assert created.json()["filename"] == "script.json"
    downloaded = client.get(created.json()["download_url"])
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"] == "application/json; charset=utf-8"
    assert "雨夜归来" in downloaded.text
    assert "content_block_id" not in downloaded.text
    assert "source_evidence_ids" not in downloaded.text
