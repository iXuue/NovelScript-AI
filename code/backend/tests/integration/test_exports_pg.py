from app.core.database import get_db
from app.models.export import ExportJob
from app.services.store import STORE


def _prepare_script(client) -> str:
    project = client.post("/projects", json={"name": "Export project"}).json()
    project_id = project["project_id"]
    upload = client.post(
        f"/projects/{project_id}/uploads",
        files={"file": ("novel.md", "# Chapter 1\n\nShe returns.\n\nThe door opens.")},
    )
    assert upload.status_code == 200
    chapter_ids = [chapter["chapter_id"] for chapter in upload.json()["detected_chapters"]]
    assert client.post(f"/projects/{project_id}/chapters/confirm", json={"chapter_ids": chapter_ids}).status_code == 200
    assert client.post(f"/projects/{project_id}/style-source", json={"kind": "builtin", "builtin_style": "suspense"}).status_code == 200
    assert client.post(f"/projects/{project_id}/scene-plan/generate").status_code == 200
    assert client.post(f"/projects/{project_id}/scene-plan/confirm", json={"confirmation_source": "button"}).status_code == 200
    assert client.post(f"/projects/{project_id}/scripts/generate").status_code == 200
    STORE.scripts.clear()
    STORE.exports.clear()
    return project_id


def test_pdf_export_returns_explicit_unavailable_error(client):
    project_id = _prepare_script(client)

    created = client.post(f"/projects/{project_id}/exports", json={"format": "pdf"})

    assert created.status_code == 400
    assert created.json()["error"]["code"] == "pdf_not_available"


def test_export_formats_share_yaml_body_but_use_different_extensions(client):
    project_id = _prepare_script(client)
    bodies = {}
    filenames = {}

    for export_format in ["yaml", "txt", "markdown"]:
        created = client.post(f"/projects/{project_id}/exports", json={"format": export_format})
        assert created.status_code == 200
        filenames[export_format] = created.json()["filename"]
        bodies[export_format] = client.get(created.json()["download_url"]).text

    assert filenames == {
        "yaml": "script.yaml",
        "txt": "script.txt",
        "markdown": "script.md",
    }
    assert len(set(bodies.values())) == 1


def test_export_docx_produces_real_docx_file(client):
    project_id = _prepare_script(client)

    created = client.post(f"/projects/{project_id}/exports", json={"format": "docx"})

    assert created.status_code == 200
    assert created.json()["filename"] == "script.docx"
    downloaded = client.get(created.json()["download_url"])
    assert downloaded.status_code == 200
    assert downloaded.content.startswith(b"PK")
    assert downloaded.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        export = db.query(ExportJob).filter(ExportJob.export_id == created.json()["export_id"]).one()
        assert export.project_id == project_id
        assert export.format == "docx"
        assert export.status == "succeeded"
    finally:
        db.close()


def test_export_clean_json_produces_json_without_internal_fields(client):
    project_id = _prepare_script(client)

    created = client.post(f"/projects/{project_id}/exports", json={"format": "clean_json"})

    assert created.status_code == 200
    assert created.json()["filename"] == "script.json"
    downloaded = client.get(created.json()["download_url"])
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"] == "application/json; charset=utf-8"
    assert "Rainy Return" in downloaded.text
    assert "content_block_id" not in downloaded.text
    assert "source_evidence_ids" not in downloaded.text
    assert "source_paragraph_ids" not in downloaded.text
