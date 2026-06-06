from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api.errors import api_error
from app.core.database import get_db
from app.models.user import User
from app.services.project_service import require_project
from app.services.run_service import get_active_run, get_run

router = APIRouter()


@router.get("/projects/{project_id}/runs/active")
def get_active_run_endpoint(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        require_project(project_id, db, current_user.user_id)
    except KeyError:
        raise api_error(404, "project_not_found", "Project not found")
    return get_active_run(project_id, db)


@router.get("/projects/{project_id}/runs/{run_id}")
def get_run_endpoint(
    project_id: str,
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        require_project(project_id, db, current_user.user_id)
    except KeyError:
        raise api_error(404, "project_not_found", "Project not found")
    run = get_run(project_id, run_id, db)
    if run is None:
        raise api_error(404, "run_not_found", "Run not found")
    return run

