from fastapi import APIRouter
from pydantic import BaseModel

from app.api.errors import api_error
from app.services.conversation_service import list_primary_messages, modify_script, send_message
from app.services.project_service import require_project

router = APIRouter()


class SendMessageRequest(BaseModel):
    content: str


class ModifyScriptRequest(BaseModel):
    message: str
    target: dict


@router.get("/projects/{project_id}/conversations/primary/messages")
def list_messages_endpoint(project_id: str):
    try:
        require_project(project_id)
        return list_primary_messages(project_id)
    except KeyError:
        raise api_error(404, "project_not_found", "Project not found")


@router.post("/projects/{project_id}/conversations/primary/messages")
def send_message_endpoint(project_id: str, payload: SendMessageRequest):
    try:
        require_project(project_id)
        return send_message(project_id, payload.content)
    except KeyError:
        raise api_error(404, "project_not_found", "Project not found")


@router.post("/projects/{project_id}/conversations/primary/modify-script")
def modify_script_endpoint(project_id: str, payload: ModifyScriptRequest):
    try:
        require_project(project_id)
        return modify_script(project_id, payload.message, payload.target)
    except KeyError:
        raise api_error(404, "project_not_found", "Project not found")
    except PermissionError:
        raise api_error(409, "scene_plan_change_required", "This change requires Scene Plan regeneration")

