from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api.errors import api_error
from app.core.database import get_db
from app.models.user import User
from app.services.export_job_service import create_export_job, get_export_job
from app.services.project_service import require_project
from app.services.run_service import create_project_run, update_run_status, update_run_step

router = APIRouter()

ALLOWED_FORMATS = {"yaml", "markdown", "docx", "pdf", "txt", "clean_json"}


class CreateExportRequest(BaseModel):
    format: str


@router.post("/projects/{project_id}/exports")
def create_export_endpoint(
    project_id: str,
    payload: CreateExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        require_project(project_id, db, current_user.user_id)
    except KeyError:
        raise api_error(404, "project_not_found", "Project not found")
    if payload.format not in ALLOWED_FORMATS:
        raise api_error(400, "validation_error", "Unsupported export format")
    try:
        export = create_export_job(db, project_id, payload.format)
    except PermissionError:
        raise api_error(409, "script_not_ready", "Script is not ready")
    except ValueError as exc:
        if str(exc) == "pdf_not_available":
            raise api_error(400, "pdf_not_available", "PDF export is not available without a PDF renderer")
        raise api_error(400, "validation_error", str(exc))
    run = create_project_run(project_id, "export", "export", ["export"], db)
    update_run_step(project_id, run["run_id"], "export", "succeeded", "Export completed", db)
    update_run_status(run["run_id"], "succeeded", db=db)
    return export


@router.get("/projects/{project_id}/exports/{export_id}")
def get_export_endpoint(
    project_id: str,
    export_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        require_project(project_id, db, current_user.user_id)
    except KeyError:
        raise api_error(404, "project_not_found", "Project not found")
    export = get_export_job(db, project_id, export_id)
    if export is None:
        raise api_error(404, "export_not_found", "Export not found")
    if export.status == "stale":
        raise api_error(409, "export_stale", "Export is stale; create a new export from the current script")
    path = Path(export.file_path)
    if not path.exists():
        raise api_error(404, "export_file_not_found", "Export file not found")
    return FileResponse(path, media_type=export.content_type, filename=export.filename)

