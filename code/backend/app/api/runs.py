from fastapi import APIRouter

from app.api.errors import api_error
from app.services.project_service import require_project
from app.services.run_service import get_active_run, get_run

router = APIRouter()


@router.get("/projects/{project_id}/runs/active")
def get_active_run_endpoint(project_id: str):
    try:
        require_project(project_id)
    except KeyError:
        raise api_error(404, "project_not_found", "Project not found")
    return get_active_run(project_id)


@router.get("/projects/{project_id}/runs/{run_id}")
def get_run_endpoint(project_id: str, run_id: str):
    try:
        require_project(project_id)
    except KeyError:
        raise api_error(404, "project_not_found", "Project not found")
    run = get_run(project_id, run_id)
    if run is None:
        raise api_error(404, "run_not_found", "Run not found")
    return run

