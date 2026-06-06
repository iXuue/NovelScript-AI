from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api.errors import api_error
from app.core.database import get_db
from app.models.user import User
from app.services.local_snapshot_service import mirror_project_snapshot
from app.services.llm_provider import LLMProvider, get_llm_provider
from app.services.orchestrator_service import confirm_scene_plan, generate_scene_plan
from app.services.project_service import require_project
from app.services.scene_plan_service import get_current_scene_plan, repair_current_scene_plan

router = APIRouter()


class ConfirmScenePlanRequest(BaseModel):
    confirmation_source: str
    message_id: str | None = None


@router.post("/projects/{project_id}/scene-plan/generate")
def generate_scene_plan_endpoint(
    project_id: str,
    db: Session = Depends(get_db),
    llm_provider: LLMProvider = Depends(get_llm_provider),
    current_user: User = Depends(get_current_user),
):
    try:
        require_project(project_id, db, current_user.user_id)
        return generate_scene_plan(project_id, db, llm_provider)
    except KeyError:
        raise api_error(404, "project_not_found", "Project not found")


@router.get("/projects/{project_id}/scene-plan")
def get_scene_plan_endpoint(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        require_project(project_id, db, current_user.user_id)
    except KeyError:
        raise api_error(404, "project_not_found", "Project not found")
    scene_plan = get_current_scene_plan(db, project_id)
    if scene_plan is None:
        raise api_error(404, "scene_plan_not_found", "Scene Plan not found")
    return scene_plan


@router.post("/projects/{project_id}/scene-plan/confirm")
def confirm_scene_plan_endpoint(
    project_id: str,
    payload: ConfirmScenePlanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        require_project(project_id, db, current_user.user_id)
        result = confirm_scene_plan(project_id, payload.confirmation_source, payload.message_id, db)
        mirror_project_snapshot(db, project_id)
        return result
    except KeyError:
        raise api_error(404, "scene_plan_not_found", "Scene Plan not found")
    except PermissionError:
        raise api_error(409, "scene_plan_validation_failed", "Scene Plan validation must pass before confirmation")


@router.post("/projects/{project_id}/scene-plan/repair")
def repair_scene_plan_endpoint(
    project_id: str,
    db: Session = Depends(get_db),
    llm_provider: LLMProvider = Depends(get_llm_provider),
    current_user: User = Depends(get_current_user),
):
    try:
        require_project(project_id, db, current_user.user_id)
        result = repair_current_scene_plan(db, project_id, llm_provider)
        mirror_project_snapshot(db, project_id)
        return result
    except KeyError:
        raise api_error(404, "scene_plan_not_found", "Scene Plan not found")
    except PermissionError as exc:
        if str(exc) == "repair_attempts_exceeded":
            raise api_error(409, "repair_attempts_exceeded", "Repair attempts exceeded")
        raise api_error(409, "scene_plan_repair_not_required", "Scene Plan repair is not required")

