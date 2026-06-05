from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.api.errors import api_error
from app.domain.artifacts import ProjectStage
from app.services.chapter_service import UploadedMarkdownDocument, assign_paragraph_ids, detect_documents_chapters
from app.services.checkpoint_service import create_checkpoint
from app.services.input_adapter import normalize_to_markdown
from app.services.project_service import require_project, update_project_stage
from app.services.store import STORE

router = APIRouter()


@router.post("/projects/{project_id}/uploads")
async def upload_novel(project_id: str, request: Request):
    try:
        require_project(project_id)
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

    chapters = detect_documents_chapters(documents)
    drafts = [chapter.to_draft() for chapter in chapters]
    STORE.chapters_pending[project_id] = drafts
    STORE.chapter_paragraphs[project_id] = [
        {"chapter_id": chapter.chapter_id, "paragraphs": chapter.paragraphs}
        for chapter in assign_paragraph_ids(chapters)
    ]
    update_project_stage(project_id, ProjectStage.chapters_pending)
    return {
        "file_id": STORE.next_id("file"),
        "project_id": project_id,
        "stage": ProjectStage.chapters_pending,
        "detected_chapters": drafts,
    }


@router.get("/projects/{project_id}/chapters/pending")
def get_pending_chapters(project_id: str):
    try:
        require_project(project_id)
    except KeyError:
        raise api_error(404, "project_not_found", "Project not found")
    return {"chapters": STORE.chapters_pending.get(project_id, [])}


class ConfirmChaptersRequest(BaseModel):
    chapter_ids: list[str]


@router.post("/projects/{project_id}/chapters/confirm")
def confirm_chapters(project_id: str, payload: ConfirmChaptersRequest):
    try:
        require_project(project_id)
    except KeyError:
        raise api_error(404, "project_not_found", "Project not found")
    pending = STORE.chapters_pending.get(project_id, [])
    available = {chapter["chapter_id"] for chapter in pending}
    if any(chapter_id not in available for chapter_id in payload.chapter_ids):
        raise api_error(400, "validation_error", "Unknown chapter id")
    checkpoint = create_checkpoint(project_id, "chapters_confirmed")
    update_project_stage(project_id, ProjectStage.chapters_confirmed)
    return {"project_id": project_id, "stage": ProjectStage.chapters_confirmed, "checkpoint_id": checkpoint["checkpoint_id"]}

