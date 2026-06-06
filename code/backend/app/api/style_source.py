from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api.errors import api_error
from app.core.database import get_db
from app.models.user import User
from app.services.project_service import require_project
from app.services.style_service import clear_style_source, get_style_source, set_style_source

router = APIRouter()


@router.post("/projects/{project_id}/style-source")
def set_style_source_endpoint(
    project_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        require_project(project_id, db, current_user.user_id)
        return set_style_source(project_id, payload, db)
    except KeyError:
        raise api_error(404, "project_not_found", "Project not found")
    except PermissionError:
        raise api_error(409, "style_source_locked", "Style source is locked after Scene Plan confirmation")
    except ValueError as exc:
        raise api_error(400, "validation_error", str(exc))


@router.get("/projects/{project_id}/style-source")
def get_style_source_endpoint(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        require_project(project_id, db, current_user.user_id)
        return get_style_source(project_id, db)
    except KeyError:
        raise api_error(404, "project_not_found", "Project not found")


@router.delete("/projects/{project_id}/style-source", status_code=204)
def clear_style_source_endpoint(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        require_project(project_id, db, current_user.user_id)
        clear_style_source(project_id, db)
        return Response(status_code=204)
    except KeyError:
        raise api_error(404, "project_not_found", "Project not found")
    except PermissionError:
        raise api_error(409, "style_source_locked", "Style source is locked after Scene Plan confirmation")

