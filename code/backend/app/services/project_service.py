from app.domain.artifacts import ProjectStage
from app.models.project import Project
from app.services.store import STORE, now_utc


def project_to_dict(project: Project) -> dict:
    return {
        "project_id": project.project_id,
        "name": project.name,
        "stage": project.stage,
        "primary_conversation_id": project.primary_conversation_id,
        "active_session_id": project.active_session_id,
        "user_id": project.user_id,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }


def cache_project(project: dict) -> dict:
    STORE.projects[project["project_id"]] = project
    STORE.conversations.setdefault(project["project_id"], [])
    return project


def create_project(db=None, name: str = "未命名项目", user_id: str | None = None) -> dict:
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
        "user_id": user_id,
        "created_at": created_at,
        "updated_at": created_at,
    }
    cache_project(project)
    if db is not None:
        db.add(
            Project(
                project_id=project_id,
                name=name,
                stage=ProjectStage.empty,
                primary_conversation_id=conversation_id,
                active_session_id=session_id,
                user_id=user_id,
                created_at=created_at,
                updated_at=created_at,
            )
        )
        db.commit()
    return project


def list_projects(db=None, user_id: str | None = None) -> list[dict]:
    if db is not None:
        query = db.query(Project)
        if user_id is not None:
            query = query.filter(Project.user_id == user_id)
        projects = query.order_by(Project.updated_at.desc()).all()
        return [cache_project(project_to_dict(project)) for project in projects]
    projects = list(STORE.projects.values())
    if user_id is not None:
        projects = [project for project in projects if project.get("user_id") == user_id]
    return projects


def get_project(project_id: str, db=None, user_id: str | None = None) -> dict | None:
    if db is not None:
        project = db.get(Project, project_id)
        if project is not None and (user_id is None or project.user_id == user_id):
            return cache_project(project_to_dict(project))
    project = STORE.projects.get(project_id)
    if project is None:
        return None
    if user_id is not None and project.get("user_id") != user_id:
        return None
    return project


def require_project(project_id: str, db=None, user_id: str | None = None) -> dict:
    project = get_project(project_id, db, user_id=user_id)
    if project is None:
        raise KeyError(project_id)
    return project


def update_project_stage(project_id: str, stage: ProjectStage) -> dict:
    project = require_project(project_id)
    project["stage"] = stage
    project["updated_at"] = now_utc()
    return project


def update_project_stage_in_db(db, project_id: str, stage: ProjectStage) -> None:
    project = db.get(Project, project_id)
    if project is not None:
        project.stage = stage
        project.updated_at = now_utc()
        db.commit()

