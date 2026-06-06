from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api.errors import api_error
from app.core.database import get_db
from app.models.user import User
from app.services.export_service import serialize_export
from app.services.project_service import require_project
from app.services.run_service import create_project_run
from app.services.store import STORE, now_utc

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
        require_project(project_id, db, user_id=current_user.user_id)
    except KeyError:
        raise api_error(404, "project_not_found", "Project not found")
    if payload.format not in ALLOWED_FORMATS:
        raise api_error(400, "validation_error", "Unsupported export format")
    script = STORE.scripts.get(project_id)
    if script is None:
        raise api_error(409, "script_not_ready", "Script is not ready")
    serialize_export(script["internal"], payload.format)
    create_project_run(project_id, "export", "export", ["export"])
    export_id = STORE.next_id("exp")
    export = {
        "export_id": export_id,
        "project_id": project_id,
        "format": payload.format,
        "status": "succeeded",
        "download_url": f"/projects/{project_id}/exports/{export_id}",
        "created_at": now_utc(),
    }
    STORE.exports[export_id] = export
    return {key: export[key] for key in ["export_id", "format", "status", "download_url"]}


@router.get("/projects/{project_id}/exports/{export_id}")
def get_export_endpoint(
    project_id: str,
    export_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        require_project(project_id, db, user_id=current_user.user_id)
    except KeyError:
        raise api_error(404, "project_not_found", "Project not found")
    export = STORE.exports.get(export_id)
    if export is None or export["project_id"] != project_id:
        raise api_error(404, "export_not_found", "Export not found")
    return export
