from app.services.store import STORE, now_utc


def create_checkpoint(project_id: str, stage: str) -> dict:
    return {
        "checkpoint_id": STORE.next_id("chk"),
        "project_id": project_id,
        "stage": stage,
        "created_at": now_utc(),
    }

