from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.errors import api_error
from app.core.database import get_db
from app.services.llm_provider import LLMProvider, get_llm_provider
from app.services.orchestrator_service import confirm_scene_plan, generate_scene_plan
from app.services.project_service import require_project
from app.services.store import STORE

router = APIRouter()


class ConfirmScenePlanRequest(BaseModel):
    confirmation_source: str
    message_id: str | None = None


@router.post("/projects/{project_id}/scene-plan/generate")
def generate_scene_plan_endpoint(
    project_id: str,
    db: Session = Depends(get_db),
    llm_provider: LLMProvider = Depends(get_llm_provider),
):
    try:
        require_project(project_id)
        return generate_scene_plan(project_id, db, llm_provider)
    except KeyError:
        raise api_error(404, "project_not_found", "Project not found")


@router.get("/projects/{project_id}/scene-plan")
def get_scene_plan_endpoint(project_id: str):
    try:
        require_project(project_id)
    except KeyError:
        raise api_error(404, "project_not_found", "Project not found")
    scene_plan = STORE.scene_plans.get(project_id)
    if scene_plan is None:
        raise api_error(404, "scene_plan_not_found", "Scene Plan not found")
    return scene_plan


@router.post("/projects/{project_id}/scene-plan/confirm")
def confirm_scene_plan_endpoint(project_id: str, payload: ConfirmScenePlanRequest):
    try:
        require_project(project_id)
        return confirm_scene_plan(project_id, payload.confirmation_source, payload.message_id)
    except KeyError:
        raise api_error(404, "scene_plan_not_found", "Scene Plan not found")

