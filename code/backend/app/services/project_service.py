import uuid

from app.domain.artifacts import ProjectStage
from app.models.project import Project
from app.services.store import STORE, now_utc


def _next_id(prefix: str, db) -> str:
    if db is not None:
        return f"{prefix}_{uuid.uuid4().hex[:8]}"
    return STORE.next_id(prefix)


def _project_to_dict(project: Project) -> dict:
    return {
        "project_id": project.project_id,
        "user_id": project.user_id,
        "name": project.name,
        "stage": project.stage,
        "primary_conversation_id": project.primary_conversation_id,
        "active_session_id": project.active_session_id,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }


def _remember_project(project: dict) -> dict:
    STORE.projects[project["project_id"]] = project
    STORE.conversations.setdefault(project["project_id"], [])
    return project


def create_project(db=None, name: str = "未命名项目", user_id: str | None = None) -> dict:
    if db is not None and user_id is None:
        raise ValueError("user_id is required")
    project_id = _next_id("proj", db)
    conversation_id = _next_id("conv", db)
    session_id = _next_id("sess", db)
    created_at = now_utc()
    project = {
        "project_id": project_id,
        "user_id": user_id,
        "name": name,
        "stage": ProjectStage.empty,
        "primary_conversation_id": conversation_id,
        "active_session_id": session_id,
        "created_at": created_at,
        "updated_at": created_at,
    }
    _remember_project(project)
    if db is not None:
        db_project = Project(
            project_id=project_id,
            user_id=user_id,
            name=name,
            stage=ProjectStage.empty,
            primary_conversation_id=conversation_id,
            active_session_id=session_id,
            created_at=created_at,
            updated_at=created_at,
        )
        db.add(db_project)
        db.commit()
        db.refresh(db_project)
        project = _remember_project(_project_to_dict(db_project))
    return project


def list_projects(db=None, user_id: str | None = None) -> list[dict]:
    if db is not None:
        query = db.query(Project)
        if user_id is not None:
            query = query.filter(Project.user_id == user_id)
        projects = [_project_to_dict(project) for project in query.order_by(Project.updated_at.desc()).all()]
        for project in projects:
            _remember_project(project)
        return projects
    projects = list(STORE.projects.values())
    if user_id is not None:
        projects = [project for project in projects if project.get("user_id") == user_id]
    return projects


def get_project(project_id: str, db=None, user_id: str | None = None) -> dict | None:
    if db is not None:
        project = db.get(Project, project_id)
        if project is None or (user_id is not None and project.user_id != user_id):
            return None
        return _remember_project(_project_to_dict(project))
    project = STORE.projects.get(project_id)
    if project is None or (user_id is not None and project.get("user_id") != user_id):
        return None
    return project


def require_project(project_id: str, db=None, user_id: str | None = None) -> dict:
    project = get_project(project_id, db, user_id)
    if project is None:
        raise KeyError(project_id)
    return project


def update_project_stage(project_id: str, stage: ProjectStage) -> dict:
    project = require_project(project_id)
    project["stage"] = stage
    project["updated_at"] = now_utc()
    return project


def delete_project(project_id: str, db=None, user_id: str | None = None) -> None:
    if db is not None:
        project = db.get(Project, project_id)
        if project is None:
            raise KeyError(project_id)
        if user_id is not None and project.user_id != user_id:
            raise PermissionError("not_owner")
        db.delete(project)
        db.commit()
    STORE.projects.pop(project_id, None)
    STORE.chapters_pending.pop(project_id, None)
    STORE.chapter_paragraphs.pop(project_id, None)
    STORE.style_sources.pop(project_id, None)
    STORE.style_locked.discard(project_id)
    for file_id, file_record in list(STORE.style_files.items()):
        if file_record.get("project_id") == project_id:
            STORE.style_files.pop(file_id, None)
    STORE.scene_plans.pop(project_id, None)
    STORE.scripts.pop(project_id, None)
    STORE.script_ui.pop(project_id, None)
    STORE.yaml_previews.pop(project_id, None)
    STORE.conversations.pop(project_id, None)
    STORE.active_run_by_project.pop(project_id, None)
    for run_id, run in list(STORE.runs.items()):
        if run.get("project_id") == project_id:
            STORE.runs.pop(run_id, None)
    for export_id, export in list(STORE.exports.items()):
        if export.get("project_id") == project_id:
            STORE.exports.pop(export_id, None)


def update_project_stage_in_db(db, project_id: str, stage: ProjectStage) -> None:
    if db is None:
        return
    project = db.get(Project, project_id)
    if project is not None:
        project.stage = stage
        project.updated_at = now_utc()
        db.commit()

