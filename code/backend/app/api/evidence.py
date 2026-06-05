from fastapi import APIRouter

from app.api.errors import api_error
from app.services.evidence_service import get_evidence_by_content_block
from app.services.project_service import require_project

router = APIRouter()


@router.get("/projects/{project_id}/evidence/by-content-block/{content_block_id}")
def get_evidence_endpoint(project_id: str, content_block_id: str):
    try:
        require_project(project_id)
    except KeyError:
        raise api_error(404, "project_not_found", "Project not found")
    return get_evidence_by_content_block(content_block_id)

