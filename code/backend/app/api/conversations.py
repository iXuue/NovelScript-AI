from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api.errors import api_error
from app.core.database import get_db
from app.models.user import User
from app.services.conversation_service import confirm_feedback_plan, create_feedback_plan, list_primary_messages, send_message
from app.services.llm_provider import LLMProvider, get_llm_provider
from app.services.project_service import require_project

router = APIRouter()


class SendMessageRequest(BaseModel):
    content: str


class ModifyScriptRequest(BaseModel):
    message: str
    target: dict


class FeedbackPlanRequest(BaseModel):
    message: str
    target: dict


@router.get("/projects/{project_id}/conversations/primary/messages")
def list_messages_endpoint(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        require_project(project_id, db, current_user.user_id)
        return list_primary_messages(project_id, db)
    except KeyError:
        raise api_error(404, "project_not_found", "Project not found")


@router.post("/projects/{project_id}/conversations/primary/messages")
def send_message_endpoint(
    project_id: str,
    payload: SendMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        require_project(project_id, db, current_user.user_id)
        return send_message(project_id, payload.content, db)
    except KeyError:
        raise api_error(404, "project_not_found", "Project not found")


@router.post("/projects/{project_id}/conversations/primary/modify-script")
def modify_script_endpoint(
    project_id: str,
    payload: ModifyScriptRequest,
    db: Session = Depends(get_db),
    llm_provider: LLMProvider = Depends(get_llm_provider),
    current_user: User = Depends(get_current_user),
):
    try:
        require_project(project_id, db, current_user.user_id)
        return create_feedback_plan(project_id, payload.message, payload.target, db, llm_provider)
    except KeyError:
        raise api_error(404, "project_not_found", "Project not found")
    except ValueError as exc:
        raise api_error(422, "invalid_feedback_target", "Invalid feedback target", {"reason": str(exc)})
    except RuntimeError as exc:
        raise api_error(502, "feedback_plan_failed", "Feedback plan generation failed", {"reason": str(exc)})
    except PermissionError:
        raise api_error(409, "scene_plan_change_required", "This change requires Scene Plan regeneration")


@router.post("/projects/{project_id}/conversations/primary/feedback-plan")
def create_feedback_plan_endpoint(
    project_id: str,
    payload: FeedbackPlanRequest,
    db: Session = Depends(get_db),
    llm_provider: LLMProvider = Depends(get_llm_provider),
    current_user: User = Depends(get_current_user),
):
    try:
        require_project(project_id, db, current_user.user_id)
        return create_feedback_plan(project_id, payload.message, payload.target, db, llm_provider)
    except KeyError:
        raise api_error(404, "project_not_found", "Project not found")
    except ValueError as exc:
        raise api_error(422, "invalid_feedback_target", "Invalid feedback target", {"reason": str(exc)})
    except RuntimeError as exc:
        raise api_error(502, "feedback_plan_failed", "Feedback plan generation failed", {"reason": str(exc)})


@router.post("/projects/{project_id}/conversations/primary/feedback-plan/{feedback_plan_id}/confirm")
def confirm_feedback_plan_endpoint(
    project_id: str,
    feedback_plan_id: str,
    db: Session = Depends(get_db),
    llm_provider: LLMProvider = Depends(get_llm_provider),
    current_user: User = Depends(get_current_user),
):
    try:
        require_project(project_id, db, current_user.user_id)
        return confirm_feedback_plan(project_id, feedback_plan_id, db, llm_provider)
    except KeyError:
        raise api_error(404, "feedback_plan_not_found", "Feedback plan not found")
    except PermissionError as exc:
        if str(exc) == "feedback_plan_stale":
            raise api_error(409, "feedback_plan_stale", "Feedback plan is stale; please create a new plan")
        if str(exc) == "script_scene_validation_failed":
            raise api_error(409, "script_scene_validation_failed", "Script scene validation failed")
        raise api_error(409, "feedback_plan_not_executable", "Feedback plan cannot be executed")
    except RuntimeError as exc:
        raise api_error(502, "feedback_plan_execution_failed", "Feedback plan execution failed", {"reason": str(exc)})

