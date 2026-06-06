from app.models.runtime import DeveloperLog
from app.services.store import now_utc
from sqlalchemy.orm import Session

SENSITIVE_KEYS = {"api_key", "database_url", "password", "secret", "token"}


def redact_sensitive(payload: dict) -> dict:
    return {key: ("<redacted>" if key.lower() in SENSITIVE_KEYS else value) for key, value in payload.items()}


def write_developer_log(run_id: str | None, payload: dict, db=None) -> None:
    if db is None:
        return None
    safe_payload = redact_sensitive(payload)
    bind = db.get_bind()
    with Session(bind=bind) as log_session:
        log_session.add(
            DeveloperLog(
                run_id=run_id,
                project_id=safe_payload.get("project_id"),
                step_type=safe_payload.get("step_type"),
                event_type=safe_payload.get("event_type") or "event",
                payload=safe_payload,
                created_at=now_utc(),
            )
        )
        log_session.commit()
    return None
