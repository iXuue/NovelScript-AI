from app.core.database import get_db
from app.models.analysis import ChapterSummary, EvidenceItem
from app.models.chapter import Chapter, Paragraph
from app.models.checkpoint import Checkpoint
from app.models.export import ExportJob
from app.models.repair import RepairAttempt
from app.models.scene_plan import ScenePlan, ScenePlanScene, ScenePlanValidation
from app.models.script import ScriptContentBlock, ScriptScene, ScriptSceneValidation, ScriptVersion
from app.models.story import StoryBible
from app.models.style import StyleProfile


NOVEL_TEXT = """# Chapter 1

She pushes open the old door.

Rain falls from the eaves.

# Chapter 2

An old letter waits on the desk.

The signature is unfamiliar.

# Chapter 3

The rain stops before dawn.

She packs every clue into her bag.
"""


def _full_pipeline(client, style_kind="builtin", style_value="suspense"):
    project = client.post("/projects", json={"name": "Rainy Return"}).json()
    project_id = project["project_id"]
    assert project["stage"] == "empty"

    upload = client.post(f"/projects/{project_id}/uploads", files={"file": ("novel.md", NOVEL_TEXT)})
    assert upload.status_code == 200
    assert [chapter["chapter_id"] for chapter in upload.json()["detected_chapters"]] == ["CH001", "CH002", "CH003"]

    pending = client.get(f"/projects/{project_id}/chapters/pending")
    assert pending.status_code == 200
    chapter_ids = [chapter["chapter_id"] for chapter in pending.json()["chapters"]]
    assert chapter_ids == ["CH001", "CH002", "CH003"]

    confirm = client.post(f"/projects/{project_id}/chapters/confirm", json={"chapter_ids": chapter_ids})
    assert confirm.status_code == 200
    assert confirm.json()["stage"] == "chapters_confirmed"

    if style_kind == "builtin":
        style = client.post(f"/projects/{project_id}/style-source", json={"kind": "builtin", "builtin_style": style_value})
    else:
        style = client.post(f"/projects/{project_id}/style-source", json={"kind": "custom_text", "style_text": style_value})
    assert style.status_code == 200

    scene_plan = client.post(f"/projects/{project_id}/scene-plan/generate")
    assert scene_plan.status_code == 200
    plan = client.get(f"/projects/{project_id}/scene-plan")
    assert plan.status_code == 200
    assert plan.json()["validation"]["passed"] is True
    assert len(plan.json()["scenes"]) == 3

    confirm_plan = client.post(f"/projects/{project_id}/scene-plan/confirm", json={"confirmation_source": "button"})
    assert confirm_plan.status_code == 200
    assert confirm_plan.json()["confirmed"] is True

    script_run = client.post(f"/projects/{project_id}/scripts/generate")
    assert script_run.status_code == 200
    current = client.get(f"/projects/{project_id}/scripts/current")
    assert current.status_code == 200
    assert current.json()["status"] == "current"

    exports = {}
    for fmt in ["yaml", "markdown", "txt", "docx", "clean_json"]:
        created = client.post(f"/projects/{project_id}/exports", json={"format": fmt})
        assert created.status_code == 200, f"export {fmt} failed"
        exports[fmt] = created.json()
        download = client.get(created.json()["download_url"])
        assert download.status_code == 200, f"download {fmt} failed"
        if fmt == "docx":
            assert download.content.startswith(b"PK")
        else:
            assert "content_block_id" not in download.text
            assert "source_evidence_ids" not in download.text
            assert "source_paragraph_ids" not in download.text

    pdf = client.post(f"/projects/{project_id}/exports", json={"format": "pdf"})
    assert pdf.status_code == 400
    assert pdf.json()["error"]["code"] == "pdf_not_available"

    return project_id, exports


def test_full_pipeline_all_artifacts_persisted(client):
    project_id, _exports = _full_pipeline(client)

    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        chapters = db.query(Chapter).filter(Chapter.project_id == project_id).order_by(Chapter.order).all()
        assert len(chapters) == 3
        assert [chapter.status for chapter in chapters] == ["confirmed", "confirmed", "confirmed"]

        paragraphs = db.query(Paragraph).filter(Paragraph.project_id == project_id).all()
        assert len(paragraphs) == 6
        paragraph_ids = {paragraph.paragraph_id for paragraph in paragraphs}

        summaries = db.query(ChapterSummary).filter(ChapterSummary.project_id == project_id).all()
        assert len(summaries) == 3
        assert db.query(EvidenceItem).filter(EvidenceItem.project_id == project_id).count() == 0
        assert db.query(StoryBible).filter(StoryBible.project_id == project_id).count() == 0

        style = db.query(StyleProfile).filter(StyleProfile.project_id == project_id).one()
        assert style.source == "builtin:suspense"

        plan = db.query(ScenePlan).filter(ScenePlan.project_id == project_id).one()
        assert plan.confirmed is True
        scenes = db.query(ScenePlanScene).filter(ScenePlanScene.scene_plan_id == plan.scene_plan_id).all()
        assert len(scenes) == 3
        validation = db.query(ScenePlanValidation).filter(ScenePlanValidation.scene_plan_id == plan.scene_plan_id).one()
        assert validation.passed is True
        assert validation.source == "deterministic"
        assert all(scene.source_evidence_ids == [] for scene in scenes)
        assert all(set(scene.source_paragraph_ids).issubset(paragraph_ids) for scene in scenes)

        version = db.query(ScriptVersion).filter(ScriptVersion.project_id == project_id).one()
        assert version.status == "current"
        script_scenes = db.query(ScriptScene).filter(ScriptScene.script_version_id == version.script_version_id).all()
        assert len(script_scenes) == len(scenes)
        content_blocks = db.query(ScriptContentBlock).filter(ScriptContentBlock.script_version_id == version.script_version_id).all()
        assert len(content_blocks) == 6
        assert all(block.source_evidence_ids == [] for block in content_blocks)
        assert all(set(block.source_paragraph_ids).issubset(paragraph_ids) for block in content_blocks)
        script_validations = (
            db.query(ScriptSceneValidation)
            .filter(ScriptSceneValidation.script_version_id == version.script_version_id)
            .all()
        )
        assert len(script_validations) == len(scenes)
        assert all(validation.passed for validation in script_validations)
        assert all(validation.source == "deterministic" for validation in script_validations)

        assert db.query(ExportJob).filter(ExportJob.project_id == project_id).count() == 5
        assert db.query(Checkpoint).filter(Checkpoint.project_id == project_id).count() >= 2
    finally:
        db.close()


def test_full_pipeline_with_custom_text_style(client):
    project_id, _exports = _full_pipeline(client, style_kind="custom_text", style_value="More suspense and faster rhythm.")

    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        style = db.query(StyleProfile).filter(StyleProfile.project_id == project_id).one()
        assert style.source == "fake-analysis"
        assert "Suspense style" in style.profile_text
    finally:
        db.close()


def test_full_pipeline_no_repair_attempts_on_clean_run(client):
    project_id, _exports = _full_pipeline(client)

    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        repairs = db.query(RepairAttempt).filter(RepairAttempt.project_id == project_id).all()
        assert repairs == []
    finally:
        db.close()


def test_full_pipeline_scene_plan_scenes_reference_valid_chapters_and_paragraphs(client):
    project_id, _exports = _full_pipeline(client)

    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        chapter_ids = {chapter.chapter_id for chapter in db.query(Chapter).filter(Chapter.project_id == project_id).all()}
        paragraph_ids = {paragraph.paragraph_id for paragraph in db.query(Paragraph).filter(Paragraph.project_id == project_id).all()}
        plan = db.query(ScenePlan).filter(ScenePlan.project_id == project_id).one()

        for scene in plan.scenes:
            assert set(scene.source_chapter_ids).issubset(chapter_ids)
            assert scene.source_evidence_ids == []
            assert set(scene.source_paragraph_ids).issubset(paragraph_ids)
    finally:
        db.close()


def test_full_pipeline_script_blocks_are_traceable_to_paragraphs(client):
    project_id, _exports = _full_pipeline(client)

    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        paragraph_ids = {paragraph.paragraph_id for paragraph in db.query(Paragraph).filter(Paragraph.project_id == project_id).all()}
        version = db.query(ScriptVersion).filter(ScriptVersion.project_id == project_id).one()

        for block in version.content_blocks:
            assert block.source_evidence_ids == []
            assert set(block.source_paragraph_ids).issubset(paragraph_ids)
    finally:
        db.close()
