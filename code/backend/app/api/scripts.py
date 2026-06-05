from fastapi import APIRouter

from app.api.errors import api_error
from app.services.orchestrator_service import generate_script
from app.services.project_service import require_project
from app.services.store import STORE

router = APIRouter()


@router.post("/projects/{project_id}/scripts/generate")
def generate_script_endpoint(project_id: str):
    try:
        require_project(project_id)
        return generate_script(project_id)
    except KeyError:
        raise api_error(404, "project_not_found", "Project not found")
    except PermissionError:
        raise api_error(409, "scene_plan_not_confirmed", "Scene Plan must be confirmed before script generation")


@router.get("/projects/{project_id}/scripts/current")
def get_current_script_endpoint(project_id: str):
    try:
        require_project(project_id)
    except KeyError:
        raise api_error(404, "project_not_found", "Project not found")
    script = STORE.script_ui.get(project_id)
    if script is None:
        raise api_error(404, "script_not_found", "Script not found")
    return script


@router.get("/projects/{project_id}/scripts/current/yaml-preview")
def get_yaml_preview_endpoint(project_id: str):
    try:
        require_project(project_id)
    except KeyError:
        raise api_error(404, "project_not_found", "Project not found")
    preview = STORE.yaml_previews.get(project_id)
    if preview is None:
        raise api_error(404, "script_not_found", "Script not found")
    return preview

