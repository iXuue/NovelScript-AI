from app.core.database import get_db
from app.models.export import ExportJob
from app.models.project import Project
from app.models.runtime import AgentRun, ConversationMessageRecord, DeveloperLog
from app.models.scene_plan import ScenePlan
from app.models.script import ScriptVersion
from app.services.store import STORE


def _create_project_with_confirmed_chapters(client, name: str, novel_text: str) -> str:
    project = client.post("/projects", json={"name": name}).json()
    project_id = project["project_id"]
    upload = client.post(f"/projects/{project_id}/uploads", files={"file": ("novel.md", novel_text)})
    assert upload.status_code == 200
    chapter_ids = [chapter["chapter_id"] for chapter in upload.json()["detected_chapters"]]
    assert client.post(f"/projects/{project_id}/chapters/confirm", json={"chapter_ids": chapter_ids}).status_code == 200
    assert client.post(f"/projects/{project_id}/style-source", json={"kind": "builtin", "builtin_style": "suspense"}).status_code == 200
    return project_id


def _create_project_with_script(client, name: str, novel_text: str) -> str:
    project_id = _create_project_with_confirmed_chapters(client, name, novel_text)
    assert client.post(f"/projects/{project_id}/scene-plan/generate").status_code == 200
    assert client.post(f"/projects/{project_id}/scene-plan/confirm", json={"confirmation_source": "button"}).status_code == 200
    assert client.post(f"/projects/{project_id}/scripts/generate").status_code == 200
    return project_id


def test_run_and_conversation_are_persisted_outside_store(client):
    project_id = _create_project_with_confirmed_chapters(client, "Runtime persistence", "# Chapter 1\n\nShe returns.")
    generated = client.post(f"/projects/{project_id}/scene-plan/generate")
    assert generated.status_code == 200
    run_id = generated.json()["run_id"]

    STORE.runs.clear()
    STORE.active_run_by_project.clear()
    run = client.get(f"/projects/{project_id}/runs/{run_id}")
    active = client.get(f"/projects/{project_id}/runs/active")
    message = client.post(f"/projects/{project_id}/conversations/primary/messages", json={"content": "Tighten suspense"})
    STORE.conversations.clear()
    messages = client.get(f"/projects/{project_id}/conversations/primary/messages")

    assert run.status_code == 200
    assert run.json()["status"] == "succeeded"
    assert [step["step_type"] for step in run.json()["steps"]] == [
        "chapter_summary",
        "style_profile",
        "scene_plan",
    ]
    assert active.status_code == 200
    assert active.json() is None
    assert message.status_code == 200
    assert messages.status_code == 200
    assert messages.json()["messages"][0]["content"] == "Tighten suspense"

    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        assert db.query(AgentRun).filter(AgentRun.project_id == project_id).count() == 1
        assert db.query(ConversationMessageRecord).filter(ConversationMessageRecord.project_id == project_id).count() == 1
        llm_logs = (
            db.query(DeveloperLog)
            .filter(DeveloperLog.project_id == project_id)
            .order_by(DeveloperLog.created_at)
            .all()
        )
        event_types = {log.event_type for log in llm_logs}
        task_types = {log.payload["task_type"] for log in llm_logs}
        assert {"llm_request_started", "llm_request_completed"}.issubset(event_types)
        assert task_types >= {"chapter_summary", "scene_plan_chapter"}
        assert "evidence_extraction" not in task_types
        assert "story_bible" not in task_types
        assert "scene_plan_validation" not in task_types
        assert all(log.run_id == run_id for log in llm_logs)
        assert all(log.payload["run_id"] == run_id for log in llm_logs)
        assert all(log.payload["prompt_characters"] <= log.payload["raw_prompt_characters"] for log in llm_logs)
        assert any(log.payload["chunk_range"]["chapter_id"] == "CH001" for log in llm_logs if log.payload["chunk_range"])
    finally:
        db.close()


def test_llm_failure_marks_run_failed_and_writes_failed_trace(client):
    project_id = _create_project_with_confirmed_chapters(client, "Failure trace", "# Chapter 1\n\nShe returns.")
    client.fake_llm_provider.fail_next_request = True

    try:
        client.post(f"/projects/{project_id}/scene-plan/generate")
    except RuntimeError:
        pass

    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        run = db.query(AgentRun).filter(AgentRun.project_id == project_id).one()
        failed_log = db.query(DeveloperLog).filter(DeveloperLog.project_id == project_id, DeveloperLog.event_type == "llm_request_failed").one()
        assert run.status == "failed"
        assert run.failure_message == "fake LLM failure"
        assert failed_log.run_id == run.run_id
        assert failed_log.payload["run_id"] == run.run_id
        assert failed_log.payload["error_type"] == "RuntimeError"
        assert failed_log.payload["error_message"] == "fake LLM failure"
    finally:
        db.close()


def test_evidence_lookup_is_scoped_to_project_current_script(client):
    project_a = _create_project_with_script(client, "Evidence A", "# Chapter 1\n\nShe returns.")
    project_b = _create_project_with_script(client, "Evidence B", "# Chapter 1\n\nA letter arrives.")

    evidence_a = client.get(f"/projects/{project_a}/evidence/by-content-block/CB001")
    evidence_b = client.get(f"/projects/{project_b}/evidence/by-content-block/CB001")

    assert evidence_a.status_code == 200
    assert evidence_b.status_code == 200
    assert evidence_a.json()["evidence"][0]["source_paragraph_id"] == "CH001_P001"
    assert evidence_b.json()["evidence"][0]["source_paragraph_id"] == "CH001_P001"
    assert evidence_a.json()["evidence"][0]["text"] == "She returns."
    assert evidence_b.json()["evidence"][0]["text"] == "A letter arrives."


def test_scene_plan_and_script_keep_versions_and_mark_exports_stale(client):
    project_id = _create_project_with_confirmed_chapters(client, "Version retention", "# Chapter 1\n\nShe returns.")
    first_plan = client.post(f"/projects/{project_id}/scene-plan/generate").json()["scene_plan_id"]
    second_plan = client.post(f"/projects/{project_id}/scene-plan/generate").json()["scene_plan_id"]
    assert first_plan != second_plan
    assert client.post(f"/projects/{project_id}/scene-plan/confirm", json={"confirmation_source": "button"}).status_code == 200
    assert client.post(f"/projects/{project_id}/scripts/generate").status_code == 200
    export = client.post(f"/projects/{project_id}/exports", json={"format": "yaml"}).json()
    assert client.post(f"/projects/{project_id}/scripts/generate").status_code == 200

    stale_download = client.get(export["download_url"])
    assert stale_download.status_code == 409
    assert stale_download.json()["error"]["code"] == "export_stale"

    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        plans = db.query(ScenePlan).filter(ScenePlan.project_id == project_id).order_by(ScenePlan.version_number).all()
        scripts = db.query(ScriptVersion).filter(ScriptVersion.project_id == project_id).order_by(ScriptVersion.version_number).all()
        export_record = db.query(ExportJob).filter(ExportJob.export_id == export["export_id"]).one()
        project = db.get(Project, project_id)

        assert [plan.version_number for plan in plans] == [1, 2]
        assert [plan.is_current for plan in plans] == [False, True]
        assert plans[0].status == "historical"
        assert [script.version_number for script in scripts] == [1, 2]
        assert [script.is_current for script in scripts] == [False, True]
        assert scripts[0].status == "historical"
        assert export_record.status == "stale"
        assert project.style_locked is True
    finally:
        db.close()
