from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api.errors import api_error
from app.core.database import get_db
from app.models.user import User
from app.services.local_snapshot_service import mirror_project_snapshot
from app.services.llm_provider import LLMProvider, get_llm_provider
from app.services.orchestrator_service import generate_script
from app.services.project_service import require_project
from app.services.script_service import get_current_script_for_ui, get_current_yaml_preview, repair_script_scene

router = APIRouter()


@router.post("/projects/{project_id}/scripts/generate")
def generate_script_endpoint(
    project_id: str,
    db: Session = Depends(get_db),
    llm_provider: LLMProvider = Depends(get_llm_provider),
    current_user: User = Depends(get_current_user),
):
    try:
        require_project(project_id, db, current_user.user_id)
        return generate_script(project_id, db, llm_provider)
    except KeyError:
        raise api_error(404, "project_not_found", "Project not found")
    except PermissionError as exc:
        if str(exc) == "script_scene_validation_failed":
            raise api_error(409, "script_scene_validation_failed", "Script scene validation failed")
        raise api_error(409, "scene_plan_not_confirmed", "Scene Plan must be confirmed before script generation")


@router.get("/projects/{project_id}/scripts/current")
def get_current_script_endpoint(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        require_project(project_id, db, current_user.user_id)
    except KeyError:
        raise api_error(404, "project_not_found", "Project not found")
    script = get_current_script_for_ui(db, project_id)
    if script is None:
        raise api_error(404, "script_not_found", "Script not found")
    return script


@router.get("/projects/{project_id}/scripts/current/yaml-preview")
def get_yaml_preview_endpoint(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        require_project(project_id, db, current_user.user_id)
    except KeyError:
        raise api_error(404, "project_not_found", "Project not found")
    preview = get_current_yaml_preview(db, project_id)
    if preview is None:
        raise api_error(404, "script_not_found", "Script not found")
    return preview


@router.post("/projects/{project_id}/scripts/scenes/{scene_id}/repair")
def repair_script_scene_endpoint(
    project_id: str,
    scene_id: str,
    db: Session = Depends(get_db),
    llm_provider: LLMProvider = Depends(get_llm_provider),
    current_user: User = Depends(get_current_user),
):
    try:
        require_project(project_id, db, current_user.user_id)
        result = repair_script_scene(db, project_id, scene_id, llm_provider)
        mirror_project_snapshot(db, project_id)
        return result
    except KeyError:
        raise api_error(404, "script_scene_not_found", "Script scene not found")
    except PermissionError as exc:
        if str(exc) == "repair_attempts_exceeded":
            raise api_error(409, "repair_attempts_exceeded", "Repair attempts exceeded")
        if str(exc) == "script_scene_repair_not_required":
            raise api_error(409, "script_scene_repair_not_required", "Script scene repair is not required")
        raise api_error(409, "scene_plan_not_confirmed", "Scene Plan must be confirmed before script repair")

