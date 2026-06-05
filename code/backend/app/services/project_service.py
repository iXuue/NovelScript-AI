from app.domain.artifacts import ProjectStage
from app.services.store import STORE, now_utc


def create_project(db=None, name: str = "未命名项目") -> dict:
    project_id = STORE.next_id("proj")
    conversation_id = STORE.next_id("conv")
    session_id = STORE.next_id("sess")
    created_at = now_utc()
    project = {
        "project_id": project_id,
        "name": name,
        "stage": ProjectStage.empty,
        "primary_conversation_id": conversation_id,
        "active_session_id": session_id,
        "created_at": created_at,
        "updated_at": created_at,
    }
    STORE.projects[project_id] = project
    STORE.conversations[project_id] = []
    return project


def list_projects() -> list[dict]:
    return list(STORE.projects.values())


def get_project(project_id: str) -> dict | None:
    return STORE.projects.get(project_id)


def require_project(project_id: str) -> dict:
    project = get_project(project_id)
    if project is None:
        raise KeyError(project_id)
    return project


def update_project_stage(project_id: str, stage: ProjectStage) -> dict:
    project = require_project(project_id)
    project["stage"] = stage
    project["updated_at"] = now_utc()
    return project

