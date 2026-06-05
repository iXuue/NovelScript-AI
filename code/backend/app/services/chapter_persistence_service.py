from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.chapter import Chapter, Paragraph
from app.services.chapter_service import DetectedChapter
from app.services.store import now_utc


def replace_project_chapters(db: Session, project_id: str, chapters: list[DetectedChapter]) -> None:
    db.execute(delete(Paragraph).where(Paragraph.project_id == project_id))
    db.execute(delete(Chapter).where(Chapter.project_id == project_id))

    timestamp = now_utc()
    for chapter in chapters:
        chapter_row = Chapter(
            project_id=project_id,
            chapter_id=chapter.chapter_id,
            title=chapter.title,
            order=chapter.order,
            raw_text=chapter.raw_text,
            paragraph_count=chapter.paragraph_count,
            status="pending",
            created_at=timestamp,
            updated_at=timestamp,
        )
        db.add(chapter_row)
        db.flush()
        for index, paragraph in enumerate(chapter.paragraphs, start=1):
            db.add(
                Paragraph(
                    project_id=project_id,
                    chapter_pk=chapter_row.id,
                    chapter_id=chapter.chapter_id,
                    paragraph_id=paragraph.paragraph_id,
                    order=index,
                    text=paragraph.text,
                    created_at=timestamp,
                )
            )
    db.commit()


def list_pending_chapter_drafts(db: Session, project_id: str) -> list[dict]:
    chapters = (
        db.query(Chapter)
        .filter(Chapter.project_id == project_id, Chapter.status == "pending")
        .order_by(Chapter.order)
        .all()
    )
    return [
        {
            "chapter_id": chapter.chapter_id,
            "title": chapter.title,
            "order": chapter.order,
            "paragraph_count": chapter.paragraph_count,
        }
        for chapter in chapters
    ]


def confirm_project_chapters(db: Session, project_id: str, chapter_ids: list[str]) -> None:
    chapters = (
        db.query(Chapter)
        .filter(Chapter.project_id == project_id, Chapter.status == "pending")
        .order_by(Chapter.order)
        .all()
    )
    by_chapter_id = {chapter.chapter_id: chapter for chapter in chapters}
    if any(chapter_id not in by_chapter_id for chapter_id in chapter_ids):
        raise ValueError("Unknown chapter id")
    if set(chapter_ids) != set(by_chapter_id):
        raise ValueError("All pending chapters must be confirmed")

    timestamp = now_utc()
    for order, chapter_id in enumerate(chapter_ids, start=1):
        chapter = by_chapter_id[chapter_id]
        chapter.order = order
        chapter.status = "confirmed"
        chapter.updated_at = timestamp
    db.commit()
