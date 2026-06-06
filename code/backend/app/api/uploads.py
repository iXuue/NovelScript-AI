from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api.errors import api_error
from app.core.database import get_db
from app.domain.artifacts import ProjectStage
from app.models.user import User
from app.services.chapter_service import UploadedMarkdownDocument, assign_paragraph_ids, detect_documents_chapters
from app.services.chapter_persistence_service import (
    confirm_project_chapters,
    list_pending_chapter_drafts,
    replace_project_chapters,
)
from app.services.checkpoint_service import create_checkpoint
from app.services.input_adapter import normalize_to_markdown
from app.services.project_service import require_project, update_project_stage, update_project_stage_in_db
from app.services.store import STORE

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
        form = await request.form()
        uploads = [item for item in [*form.getlist("files"), *form.getlist("file")] if hasattr(item, "read")]
        if not uploads:
            raise ValueError("file field is required")
        documents = []
        for upload in uploads:
            content = await upload.read()
            documents.append(
                UploadedMarkdownDocument(
                    filename=upload.filename or "upload.txt",
                    markdown=normalize_to_markdown(upload.filename or "upload.txt", content),
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
    update_project_stage(project_id, ProjectStage.chapters_pending)
    update_project_stage_in_db(db, project_id, ProjectStage.chapters_pending)
    return {
        "file_id": STORE.next_id("file"),
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

