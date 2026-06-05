from app.services.run_service import create_project_run
from app.services.store import STORE, now_utc


def list_primary_messages(project_id: str) -> dict:
    project = STORE.projects[project_id]
    return {
        "conversation_id": project["primary_conversation_id"],
        "messages": STORE.conversations.get(project_id, []),
    }


def send_message(project_id: str, content: str) -> dict:
    project = STORE.projects[project_id]
    message = {
        "message_id": STORE.next_id("msg"),
        "conversation_id": project["primary_conversation_id"],
        "role": "user",
        "content": content,
        "created_at": now_utc(),
    }
    STORE.conversations.setdefault(project_id, []).append(message)
    return message


def modify_script(project_id: str, message: str, target: dict) -> dict:
    if target.get("type") == "scene" and target.get("scene_id"):
        send_message(project_id, message)
        run = create_project_run(project_id, "conversation_edit", "conversation_edit", ["conversation_edit", "validation"])
        return {"run_id": run["run_id"], "status": "running", "stage": "conversation_edit"}
    raise PermissionError("scene_plan_change_required")

