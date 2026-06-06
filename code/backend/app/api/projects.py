from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api.errors import api_error
from app.core.database import get_db
from app.models.user import User
from app.services.local_snapshot_service import mirror_project_snapshot
from app.services.project_service import create_project, get_project, list_projects

router = APIRouter()


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1)


@router.post("/projects")
def create_project_endpoint(
    payload: CreateProjectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = create_project(db, name=payload.name, user_id=current_user.user_id)
    mirror_project_snapshot(db, project["project_id"])
    return project


@router.get("/projects")
def list_projects_endpoint(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return list_projects(db, current_user.user_id)


@router.get("/projects/{project_id}")
def get_project_endpoint(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = get_project(project_id, db, current_user.user_id)
    if project is None:
        raise api_error(404, "project_not_found", "Project not found")
    return project

