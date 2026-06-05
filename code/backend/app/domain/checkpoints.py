from datetime import datetime

from pydantic import BaseModel


class Checkpoint(BaseModel):
    checkpoint_id: str
    project_id: str
    stage: str
    created_at: datetime

