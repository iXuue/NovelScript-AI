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
