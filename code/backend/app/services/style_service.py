from pydantic import TypeAdapter, ValidationError

from app.domain.artifacts import ProjectStage
from app.domain.style import StyleSource
from app.services.project_service import update_project_stage
from app.services.store import STORE


STYLE_ADAPTER = TypeAdapter(StyleSource)


def validate_style_source(data: dict) -> StyleSource:
    if data.get("kind") == "custom":
        raise ValueError("style source kind must be builtin, custom_text, or reference_scripts")
    if data.get("style_text") and data.get("reference_file_ids"):
        raise ValueError("style_text and reference_file_ids are mutually exclusive")
    try:
        return STYLE_ADAPTER.validate_python(data)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc


def set_style_source(project_id: str, data: dict) -> dict:
    if project_id in STORE.style_locked:
        raise PermissionError("style_source_locked")
    source = validate_style_source(data)
    source_dict = source.model_dump()
    STORE.style_sources[project_id] = source_dict
    update_project_stage(project_id, ProjectStage.style_selected)
    return {
        "project_id": project_id,
        "style_source": source_dict,
        "style_locked": False,
        "stage": ProjectStage.style_selected,
    }


def get_style_source(project_id: str) -> dict:
    return {
        "project_id": project_id,
        "style_source": STORE.style_sources.get(project_id),
        "style_locked": project_id in STORE.style_locked,
    }


def clear_style_source(project_id: str) -> None:
    if project_id in STORE.style_locked:
        raise PermissionError("style_source_locked")
    STORE.style_sources.pop(project_id, None)


def upload_style_reference(project_id: str, filename: str) -> dict:
    if project_id in STORE.style_locked:
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
    return payload


def lock_style_source(project_id: str) -> None:
    STORE.style_locked.add(project_id)

