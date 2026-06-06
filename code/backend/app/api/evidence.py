from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api.errors import api_error
from app.core.database import get_db
from app.models.user import User
from app.services.evidence_service import get_evidence_by_content_block
from app.services.project_service import require_project

router = APIRouter()


@router.get("/projects/{project_id}/evidence/by-content-block/{content_block_id}")
def get_evidence_endpoint(
    project_id: str,
    content_block_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        require_project(project_id, db, current_user.user_id)
    except KeyError:
        raise api_error(404, "project_not_found", "Project not found")
    return get_evidence_by_content_block(content_block_id, project_id, db)

