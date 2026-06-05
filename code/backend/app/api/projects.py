from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.errors import api_error
from app.services.project_service import create_project, get_project, list_projects

router = APIRouter()


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1)


@router.post("/projects")
def create_project_endpoint(payload: CreateProjectRequest):
    return create_project(name=payload.name)


@router.get("/projects")
def list_projects_endpoint():
    return list_projects()


@router.get("/projects/{project_id}")
def get_project_endpoint(project_id: str):
    project = get_project(project_id)
    if project is None:
        raise api_error(404, "project_not_found", "Project not found")
    return project

