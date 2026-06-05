from pathlib import Path

from app.core.config import get_settings


def storage_root() -> Path:
    return Path(get_settings().storage_root)


def developer_run_dir(run_id: str) -> Path:
    return storage_root() / "developer_runs" / run_id


def export_dir(project_id: str) -> Path:
    return storage_root() / "exports" / project_id

