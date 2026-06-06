from app.core.database import get_db
from app.models.analysis import ChapterSummary, EvidenceItem


def test_scene_plan_generation_persists_chapter_summaries_without_evidence_items(client):
    project = client.post("/projects", json={"name": "Analysis project"}).json()
    project_id = project["project_id"]
    upload = client.post(
        f"/projects/{project_id}/uploads",
        files={
            "file": (
                "novel.md",
                "# Chapter 1\n\nShe returns.\n\nThe door opens.\n\n# Chapter 2\n\nThe letter is old.",
            )
        },
    )
    chapter_ids = [chapter["chapter_id"] for chapter in upload.json()["detected_chapters"]]
    confirm = client.post(f"/projects/{project_id}/chapters/confirm", json={"chapter_ids": chapter_ids})
    assert confirm.status_code == 200

    scene_plan = client.post(f"/projects/{project_id}/scene-plan/generate")

    assert scene_plan.status_code == 200
    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        summaries = (
            db.query(ChapterSummary)
            .filter(ChapterSummary.project_id == project_id)
            .order_by(ChapterSummary.chapter_id)
            .all()
        )
        evidence_items = (
            db.query(EvidenceItem)
            .filter(EvidenceItem.project_id == project_id)
            .order_by(EvidenceItem.evidence_id)
            .all()
        )

        assert [summary.chapter_id for summary in summaries] == ["CH001", "CH002"]
        assert summaries[0].summary == "Chapter summary"
        assert summaries[0].source == "fake-analysis"
        task_types = [request.task_type for request in client.fake_llm_provider.requests]
        assert task_types.count("chapter_summary") == 2
        assert task_types.count("scene_plan_chapter") == 2
        assert "evidence_extraction" not in task_types
        assert evidence_items == []
    finally:
        db.close()
