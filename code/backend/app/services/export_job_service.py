from pathlib import Path

from app.core.paths import export_dir
from app.models.export import ExportJob
from app.services.export_service import EXPORT_CONTENT_TYPES, EXPORT_EXTENSIONS, serialize_export
from app.services.script_service import get_current_internal_script
from app.services.store import STORE, now_utc


def create_export_job(db, project_id: str, export_format: str) -> dict:
    current = get_current_internal_script(db, project_id)
    if current is None:
        raise PermissionError("script_not_ready")
    script_version, internal = current
    content = serialize_export(internal, export_format)
    export_id = STORE.next_id("exp")
    filename = f"script.{EXPORT_EXTENSIONS[export_format]}"
    target_dir = export_dir(project_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / f"{export_id}-{filename}"
    _write_text_file(file_path, content)
    export = ExportJob(
        export_id=export_id,
        project_id=project_id,
        script_version_id=script_version.script_version_id,
        format=export_format,
        status="succeeded",
        filename=filename,
        content_type=EXPORT_CONTENT_TYPES[export_format],
        file_path=str(file_path),
        created_at=now_utc(),
    )
    db.add(export)
    db.commit()
    return export_to_dict(export)


def get_export_job(db, project_id: str, export_id: str) -> ExportJob | None:
    return (
        db.query(ExportJob)
        .filter(ExportJob.project_id == project_id, ExportJob.export_id == export_id)
        .one_or_none()
    )


def export_to_dict(export: ExportJob) -> dict:
    return {
        "export_id": export.export_id,
        "format": export.format,
        "status": export.status,
        "filename": export.filename,
        "download_url": f"/projects/{export.project_id}/exports/{export.export_id}",
    }


def _write_text_file(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
