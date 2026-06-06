from app.services.store import STORE


def _prepare_script_project(client, name: str, source_text: str) -> str:
    project = client.post("/projects", json={"name": name}).json()
    project_id = project["project_id"]
    upload = client.post(
        f"/projects/{project_id}/uploads",
        files={"file": ("novel.md", f"# Chapter 1\n\n{source_text}")},
    )
    assert upload.status_code == 200
    chapter_ids = [chapter["chapter_id"] for chapter in upload.json()["detected_chapters"]]
    assert client.post(f"/projects/{project_id}/chapters/confirm", json={"chapter_ids": chapter_ids}).status_code == 200
    assert client.post(f"/projects/{project_id}/style-source", json={"kind": "builtin", "builtin_style": "suspense"}).status_code == 200
    assert client.post(f"/projects/{project_id}/scene-plan/generate").status_code == 200
    assert client.post(f"/projects/{project_id}/scene-plan/confirm", json={"confirmation_source": "button"}).status_code == 200
    assert client.post(f"/projects/{project_id}/scripts/generate").status_code == 200
    return project_id


def test_project_artifacts_can_be_reloaded_from_db_after_store_project_cache_is_cleared(client):
    project_id = _prepare_script_project(client, "Reloadable project", "alpha source line")

    STORE.reset()

    projects = client.get("/projects")
    assert projects.status_code == 200
    assert [project["project_id"] for project in projects.json()] == [project_id]

    project = client.get(f"/projects/{project_id}")
    assert project.status_code == 200
    assert project.json()["stage"] == "script_ready"

    style = client.get(f"/projects/{project_id}/style-source")
    assert style.status_code == 200
    assert style.json()["style_source"] == {"kind": "builtin", "builtin_style": "suspense"}
    assert style.json()["style_locked"] is True

    scene_plan = client.get(f"/projects/{project_id}/scene-plan")
    assert scene_plan.status_code == 200
    assert scene_plan.json()["confirmed"] is True

    preview = client.get(f"/projects/{project_id}/scripts/current/yaml-preview")
    assert preview.status_code == 200
    assert "yaml" in preview.json()

    active_run = client.get(f"/projects/{project_id}/runs/active")
    assert active_run.status_code == 200
    assert active_run.json() is None


def test_evidence_lookup_uses_current_project_and_script_version(client):
    first_project_id = _prepare_script_project(client, "First project", "first project source")
    second_project_id = _prepare_script_project(client, "Second project", "second project source")

    first_evidence = client.get(f"/projects/{first_project_id}/evidence/by-content-block/CB001")
    second_evidence = client.get(f"/projects/{second_project_id}/evidence/by-content-block/CB001")

    assert first_evidence.status_code == 200
    assert second_evidence.status_code == 200
    assert first_evidence.json()["evidence"][0]["source_evidence_id"] == "EV001"
    assert first_evidence.json()["evidence"][0]["chapter_id"] == "CH001"
    assert first_evidence.json()["evidence"][0]["paragraph_id"] == "CH001_P001"
    assert first_evidence.json()["evidence"][0]["text"] == "first project source"
    assert second_evidence.json()["evidence"][0]["text"] == "second project source"


def test_modify_script_accepts_script_target_and_rejects_structural_targets(client):
    project_id = _prepare_script_project(client, "Editable project", "editable source")

    accepted = client.post(
        f"/projects/{project_id}/conversations/primary/modify-script",
        json={"message": "make the whole script tighter", "target": {"type": "script"}},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "running"
    assert accepted.json()["stage"] == "conversation_edit"
    assert accepted.json()["run_id"]

    rejected = client.post(
        f"/projects/{project_id}/conversations/primary/modify-script",
        json={"message": "merge scenes", "target": {"type": "chapter", "chapter_id": "CH001"}},
    )
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "scene_plan_change_required"
