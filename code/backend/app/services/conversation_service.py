from app.models.project import Project
from app.models.runtime import ConversationMessageRecord
from app.services.run_service import create_project_run
from app.services.store import STORE, now_utc, persistent_id


def _message_to_dict(message: ConversationMessageRecord) -> dict:
    return {
        "message_id": message.message_id,
        "conversation_id": message.conversation_id,
        "role": message.role,
        "content": message.content,
        "created_at": message.created_at,
    }


def list_primary_messages(project_id: str, db=None) -> dict:
    if db is not None:
        project = db.get(Project, project_id)
        if project is None:
            raise KeyError(project_id)
        messages = (
            db.query(ConversationMessageRecord)
            .filter(
                ConversationMessageRecord.project_id == project_id,
                ConversationMessageRecord.conversation_id == project.primary_conversation_id,
            )
            .order_by(ConversationMessageRecord.created_at, ConversationMessageRecord.message_id)
            .all()
        )
        return {"conversation_id": project.primary_conversation_id, "messages": [_message_to_dict(message) for message in messages]}

    project = STORE.projects[project_id]
    return {
        "conversation_id": project["primary_conversation_id"],
        "messages": STORE.conversations.get(project_id, []),
    }


def send_message(project_id: str, content: str, db=None) -> dict:
    if db is not None:
        project = db.get(Project, project_id)
        if project is None:
            raise KeyError(project_id)
        message = ConversationMessageRecord(
            message_id=persistent_id("msg"),
            project_id=project_id,
            conversation_id=project.primary_conversation_id,
            role="user",
            content=content,
            created_at=now_utc(),
        )
        db.add(message)
        db.commit()
        db.refresh(message)
        return _message_to_dict(message)

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


def modify_script(project_id: str, message: str, target: dict, db=None) -> dict:
    if target.get("type") in {"scene", "chapter", "script"}:
        send_message(project_id, message, db)
        run = create_project_run(project_id, "conversation_edit", "conversation_edit", ["conversation_edit", "validation"], db)
        return {"run_id": run["run_id"], "status": "running", "stage": "conversation_edit"}
    raise PermissionError("scene_plan_change_required")
