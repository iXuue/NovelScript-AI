import json

from app.domain.artifacts import ProjectStage
from app.models.analysis import ChapterSummary, EvidenceItem
from app.models.chapter import Chapter, Paragraph
from app.models.project import Project
from app.models.user import User
from app.services import local_snapshot_service
from app.services.local_snapshot_service import mirror_project_snapshot, save_project_snapshot_from_pg
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
        title="Chapter 1",
        order=1,
        raw_text="She returns.",
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
            text="She returns.",
            created_at=timestamp,
        )
    )
    test_db.add(
        ChapterSummary(
            project_id=project_id,
            chapter_id="CH001",
            title="Chapter 1",
            summary="She returns on a rainy night.",
            key_events=["Return"],
            characters=["She"],
            locations=["Old house"],
            conflicts=["Whether she enters"],
            foreshadowing=["Old letter"],
            adaptation_suggestions=["Keep the rainy night"],
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
            quote="She returns.",
            evidence_type="key_event",
            explanation="The protagonist returns and moves the plot.",
            related_characters=["She"],
            related_locations=["Old house"],
            related_plot_points=["Return"],
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

    assert summaries[0]["summary"] == "She returns on a rainy night."
    assert evidence[0]["evidence_id"] == "EV001"
    assert evidence[0]["paragraph_ids"] == ["CH001_P001"]
    assert "paragraph_id" not in evidence[0]
    assert evidence[0]["quote"] == "She returns."
    assert paragraphs[0]["paragraphs"][0]["text"] == "She returns."


def test_mirror_project_snapshot_rolls_back_session_after_snapshot_failure(monkeypatch):
    class SessionStub:
        def __init__(self):
            self.rollback_called = False

        def rollback(self):
            self.rollback_called = True

    def fail_snapshot(db, project_id):
        raise RuntimeError("snapshot failed")

    session = SessionStub()
    monkeypatch.setattr(local_snapshot_service, "snapshot_enabled", lambda: True)
    monkeypatch.setattr(local_snapshot_service, "save_project_snapshot_from_pg", fail_snapshot)

    mirror_project_snapshot(session, "proj_snapshot")

    assert session.rollback_called is True
