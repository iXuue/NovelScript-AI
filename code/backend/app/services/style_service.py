from pydantic import TypeAdapter, ValidationError

from app.domain.artifacts import ArtifactStatus, ProjectStage
from app.models.scene_plan import ScenePlan
from app.domain.style import StyleSource
from app.models.style import StyleReferenceFile, StyleSourceRecord
from app.services.project_service import update_project_stage
from app.services.store import STORE
from app.services.store import now_utc


STYLE_ADAPTER = TypeAdapter(StyleSource)


def is_style_locked(project_id: str, db=None) -> bool:
    if project_id in STORE.style_locked:
        return True
    if db is None:
        return False
    confirmed_plan = (
        db.query(ScenePlan)
        .filter(
            ScenePlan.project_id == project_id,
            ScenePlan.status == ArtifactStatus.current,
            ScenePlan.confirmed.is_(True),
        )
        .one_or_none()
    )
    return confirmed_plan is not None


def validate_style_source(data: dict) -> StyleSource:
    if data.get("kind") == "custom":
        raise ValueError("style source kind must be builtin, custom_text, or reference_scripts")
    if data.get("style_text") and data.get("reference_file_ids"):
        raise ValueError("style_text and reference_file_ids are mutually exclusive")
    try:
        return STYLE_ADAPTER.validate_python(data)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc


def set_style_source(project_id: str, data: dict, db=None) -> dict:
    if is_style_locked(project_id, db):
        raise PermissionError("style_source_locked")
    source = validate_style_source(data)
    source_dict = source.model_dump()
    STORE.style_sources[project_id] = source_dict
    if db is not None:
        timestamp = now_utc()
        record = db.get(StyleSourceRecord, project_id)
        if record is None:
            record = StyleSourceRecord(
                project_id=project_id,
                kind=source_dict["kind"],
                builtin_style=source_dict.get("builtin_style"),
                style_text=source_dict.get("style_text"),
                reference_file_ids=source_dict.get("reference_file_ids") or [],
                created_at=timestamp,
                updated_at=timestamp,
            )
            db.add(record)
        else:
            record.kind = source_dict["kind"]
            record.builtin_style = source_dict.get("builtin_style")
            record.style_text = source_dict.get("style_text")
            record.reference_file_ids = source_dict.get("reference_file_ids") or []
            record.updated_at = timestamp
        db.commit()
    update_project_stage(project_id, ProjectStage.style_selected)
    return {
        "project_id": project_id,
        "style_source": source_dict,
        "style_locked": is_style_locked(project_id, db),
        "stage": ProjectStage.style_selected,
    }


def get_style_source(project_id: str, db=None) -> dict:
    style_source = STORE.style_sources.get(project_id)
    if db is not None:
        record = db.get(StyleSourceRecord, project_id)
        if record is not None:
            if record.kind == "builtin":
                style_source = {"kind": "builtin", "builtin_style": record.builtin_style}
            elif record.kind == "custom_text":
                style_source = {"kind": "custom_text", "style_text": record.style_text}
            else:
                style_source = {"kind": "reference_scripts", "reference_file_ids": record.reference_file_ids}
    return {
        "project_id": project_id,
        "style_source": style_source,
        "style_locked": is_style_locked(project_id, db),
    }


def clear_style_source(project_id: str, db=None) -> None:
    if is_style_locked(project_id, db):
        raise PermissionError("style_source_locked")
    STORE.style_sources.pop(project_id, None)
    if db is not None:
        record = db.get(StyleSourceRecord, project_id)
        if record is not None:
            db.delete(record)
            db.commit()


def upload_style_reference(project_id: str, filename: str, markdown: str = "", db=None) -> dict:
    if is_style_locked(project_id, db):
        raise PermissionError("style_source_locked")
    file_id = STORE.next_id("file_style")
    payload = {
        "file_id": file_id,
        "project_id": project_id,
        "purpose": "style_reference",
        "filename": filename,
        "stage": STORE.projects[project_id]["stage"],
    }
    STORE.style_files[file_id] = payload
    if db is not None:
        db.add(
            StyleReferenceFile(
                file_id=file_id,
                project_id=project_id,
                filename=filename,
                markdown=markdown,
                created_at=now_utc(),
            )
        )
        db.commit()
    return payload


def lock_style_source(project_id: str) -> None:
    STORE.style_locked.add(project_id)

