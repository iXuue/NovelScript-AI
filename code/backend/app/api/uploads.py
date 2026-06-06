from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api.errors import api_error
from app.core.config import get_settings
from app.core.database import get_db
from app.domain.artifacts import ProjectStage
from app.models.runtime import SourceFileRecord
from app.models.user import User
from app.services.chapter_service import UploadedMarkdownDocument, assign_paragraph_ids, detect_documents_chapters
from app.services.chapter_persistence_service import (
    confirm_project_chapters,
    list_pending_chapter_drafts,
    replace_project_chapters,
)
from app.services.checkpoint_service import create_checkpoint
from app.services.input_adapter import normalize_to_markdown, parse_multipart_files
from app.services.project_service import require_project, update_project_stage, update_project_stage_in_db
from app.services.store import STORE, now_utc, persistent_id

router = APIRouter()


@router.post("/projects/{project_id}/uploads")
async def upload_novel(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        require_project(project_id, db, current_user.user_id)
        uploads = parse_multipart_files(await request.body(), request.headers.get("content-type", ""))
        if not uploads:
            raise ValueError("file field is required")
        settings = get_settings()
        documents = []
        source_files = []
        total_characters = 0
        for upload in uploads:
            markdown = normalize_to_markdown(upload.filename or "upload.txt", upload.content)
            total_characters += len(markdown)
            if total_characters > settings.max_upload_characters:
                raise ValueError(f"upload exceeds max character budget: {settings.max_upload_characters}")
            file_id = persistent_id("file")
            source_files.append(
                SourceFileRecord(
                    file_id=file_id,
                    project_id=project_id,
                    purpose="novel_upload",
                    filename=upload.filename or "upload.txt",
                    content_type=getattr(upload, "content_type", None),
                    character_count=len(markdown),
                    created_at=now_utc(),
                )
            )
            documents.append(
                UploadedMarkdownDocument(
                    filename=upload.filename or "upload.txt",
                    markdown=markdown,
                )
            )
    except KeyError:
        raise api_error(404, "project_not_found", "Project not found")
    except ValueError as exc:
        code = "unsupported_media_type" if "unsupported" in str(exc) or ".doc" in str(exc) else "validation_error"
        raise api_error(415 if code == "unsupported_media_type" else 400, code, str(exc))

    chapters = assign_paragraph_ids(detect_documents_chapters(documents))
    drafts = [chapter.to_draft() for chapter in chapters]
    STORE.chapters_pending[project_id] = drafts
    STORE.chapter_paragraphs[project_id] = [
        {"chapter_id": chapter.chapter_id, "paragraphs": chapter.paragraphs}
        for chapter in chapters
    ]
    replace_project_chapters(db, project_id, chapters)
    for source_file in source_files:
        db.add(source_file)
    db.commit()
    update_project_stage(project_id, ProjectStage.chapters_pending)
    update_project_stage_in_db(db, project_id, ProjectStage.chapters_pending)
    return {
        "file_id": source_files[0].file_id,
        "project_id": project_id,
        "stage": ProjectStage.chapters_pending,
        "detected_chapters": drafts,
    }


@router.get("/projects/{project_id}/chapters/pending")
def get_pending_chapters(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        require_project(project_id, db, current_user.user_id)
    except KeyError:
        raise api_error(404, "project_not_found", "Project not found")
    return {"chapters": list_pending_chapter_drafts(db, project_id)}


class ConfirmChaptersRequest(BaseModel):
    chapter_ids: list[str]


@router.post("/projects/{project_id}/chapters/confirm")
def confirm_chapters(
    project_id: str,
    payload: ConfirmChaptersRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        require_project(project_id, db, current_user.user_id)
    except KeyError:
        raise api_error(404, "project_not_found", "Project not found")
    try:
        confirm_project_chapters(db, project_id, payload.chapter_ids)
    except ValueError as exc:
        raise api_error(400, "validation_error", str(exc))
    checkpoint = create_checkpoint(project_id, "chapters_confirmed", db)
    update_project_stage(project_id, ProjectStage.chapters_confirmed)
    update_project_stage_in_db(db, project_id, ProjectStage.chapters_confirmed)
    return {"project_id": project_id, "stage": ProjectStage.chapters_confirmed, "checkpoint_id": checkpoint["checkpoint_id"]}

