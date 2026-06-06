import json

from app.domain.artifacts import ProjectStage
from app.models.analysis import ChapterSummary, EvidenceItem
from app.models.chapter import Chapter, Paragraph
from app.models.project import Project
from app.models.user import User
from app.services.local_snapshot_service import save_project_snapshot_from_pg
from app.services.store import now_utc


def test_pg_snapshot_writes_chapter_summaries_and_evidence_items(test_db, tmp_path):
    timestamp = now_utc()
    project_id = "proj_snapshot"
    user_id = "user_snapshot"
    test_db.add(
        User(
            user_id=user_id,
            login_id="snapshot",
            password_hash="hash",
            password_salt="salt",
            created_at=timestamp,
            updated_at=timestamp,
        )
    )
    test_db.add(
        Project(
            project_id=project_id,
            user_id=user_id,
            name="Snapshot Project",
            stage=ProjectStage.chapters_confirmed,
            primary_conversation_id="conv_snapshot",
            active_session_id="sess_snapshot",
            created_at=timestamp,
            updated_at=timestamp,
        )
    )
    chapter = Chapter(
        project_id=project_id,
        chapter_id="CH001",
        title="第一章",
        order=1,
        raw_text="她回来了。",
        paragraph_count=1,
        status="confirmed",
        created_at=timestamp,
        updated_at=timestamp,
    )
    test_db.add(chapter)
    test_db.flush()
    test_db.add(
        Paragraph(
            project_id=project_id,
            chapter_pk=chapter.id,
            chapter_id="CH001",
            paragraph_id="CH001_P001",
            order=1,
            text="她回来了。",
            created_at=timestamp,
        )
    )
    test_db.add(
        ChapterSummary(
            project_id=project_id,
            chapter_id="CH001",
            title="第一章",
            summary="她在雨夜归来。",
            key_events=["归来"],
            characters=["她"],
            locations=["旧宅"],
            conflicts=["是否进门"],
            foreshadowing=["旧信"],
            adaptation_suggestions=["保留雨夜"],
            source="fake",
            created_at=timestamp,
            updated_at=timestamp,
        )
    )
    test_db.add(
        EvidenceItem(
            project_id=project_id,
            evidence_id="EV001",
            chapter_id="CH001",
            paragraph_id="CH001_P001",
            paragraph_ids=["CH001_P001"],
            quote="她回来了。",
            evidence_type="关键事件",
            explanation="主角归来推动剧情。",
            related_characters=["她"],
            related_locations=["旧宅"],
            related_plot_points=["归来"],
            importance=5,
            must_keep=True,
            source="fake",
            created_at=timestamp,
            updated_at=timestamp,
        )
    )
    test_db.commit()

    project_dir = save_project_snapshot_from_pg(test_db, project_id, tmp_path)

    summaries = json.loads((project_dir / "chapter_summaries.json").read_text(encoding="utf-8"))
    evidence = json.loads((project_dir / "evidence_items.json").read_text(encoding="utf-8"))
    paragraphs = json.loads((project_dir / "paragraphs.json").read_text(encoding="utf-8"))

    assert summaries[0]["summary"] == "她在雨夜归来。"
    assert evidence[0]["evidence_id"] == "EV001"
    assert evidence[0]["paragraph_ids"] == ["CH001_P001"]
    assert "paragraph_id" not in evidence[0]
    assert evidence[0]["quote"] == "她回来了。"
    assert paragraphs[0]["paragraphs"][0]["text"] == "她回来了。"
