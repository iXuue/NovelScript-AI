from datetime import datetime

from pydantic import BaseModel

from app.domain.artifacts import ProjectStage


class ProjectSummary(BaseModel):
    project_id: str
    name: str
    stage: ProjectStage
    primary_conversation_id: str
    active_session_id: str
    created_at: datetime
    updated_at: datetime


class ChapterDraft(BaseModel):
    chapter_id: str
    title: str
    order: int
    paragraph_count: int

