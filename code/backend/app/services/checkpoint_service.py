from app.models.checkpoint import Checkpoint
from app.services.store import STORE, now_utc, persistent_id


def create_checkpoint(project_id: str, stage: str, db=None) -> dict:
    source = persistent_id if db is not None else STORE.next_id
    checkpoint = {
        "checkpoint_id": source("chk"),
        "project_id": project_id,
        "stage": stage,
        "created_at": now_utc(),
    }
    if db is not None:
        db.add(Checkpoint(**checkpoint))
        db.commit()
    return checkpoint

