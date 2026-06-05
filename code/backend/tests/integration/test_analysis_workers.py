from app.core.database import get_db
from app.models.analysis import ChapterSummary, EvidenceItem


def test_scene_plan_generation_persists_chapter_summaries_and_evidence_from_confirmed_chapters(client):
    project = client.post("/projects", json={"name": "分析项目"}).json()
    project_id = project["project_id"]
    upload = client.post(
        f"/projects/{project_id}/uploads",
        files={
            "file": (
                "novel.md",
                "# 第一章 雨夜\n\n她回来了。\n\n门开了。\n\n# 第二章 旧信\n\n信封泛黄。",
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
        assert summaries[0].summary == "LLM章节摘要"
        assert summaries[0].source == "fake-analysis"
        task_types = [request.task_type for request in client.fake_llm_provider.requests]
        assert task_types.count("chapter_summary") == 2
        assert task_types.count("evidence_extraction") == 2
        assert [item.evidence_id for item in evidence_items] == ["EV001", "EV002"]
        assert evidence_items[0].paragraph_id == "CH001_P001"
        assert evidence_items[0].evidence_type == "关键事件"
        assert evidence_items[0].explanation == "主角归来推动剧情。"
        assert evidence_items[0].importance == 5
        assert evidence_items[0].must_keep is True
    finally:
        db.close()
