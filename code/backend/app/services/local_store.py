"""本地文件持久化层 —— 将项目数据序列化到 data/<项目名>/ 目录。

仅在 USE_LOCAL_STORAGE=true 时启用。不依赖 PostgreSQL。
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, data: Any) -> None:
    _ensure_dir(path.parent)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, default=_json_default)
    os.replace(tmp, path)


def _read_json(path: Path) -> Any:
    if not path.is_file():
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _json_default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _safe_dirname(name: str) -> str:
    """将项目名转为安全的目录名。"""
    unsafe = '<>:"/\\|?*'
    sanitized = "".join("_" if ch in unsafe else ch for ch in name).strip()
    return sanitized or "unnamed"


def project_data_dir(data_root: str, project_name: str, project_id: str) -> Path:
    """返回项目的本地数据目录路径。

    格式: data/<项目名>_<project_id 短后缀>/
    确保不同项目不会冲突。
    """
    short_id = project_id.split("_")[-1][:8] if "_" in project_id else project_id[:8]
    dirname = f"{_safe_dirname(project_name)}_{short_id}"
    return Path(data_root) / dirname


def save_project(data_root: str, project_name: str, project: dict, chapters: list[dict] | None,
                 chapter_paragraphs: list[dict] | None, style_source: dict | None,
                 scene_plan: dict | None, script_internal: dict | None,
                 script_ui: dict | None, yaml_preview: dict | None,
                 evidence_map: dict[str, Any], conversations: list[dict],
                 runs: dict[str, Any], exports: dict[str, Any]) -> Path:
    """将单个项目的全部数据写入本地目录。"""
    project_dir = project_data_dir(data_root, project_name, project["project_id"])
    _ensure_dir(project_dir)

    _write_json(project_dir / "project.json", project)

    if chapters is not None:
        _write_json(project_dir / "chapters.json", chapters)
    if chapter_paragraphs is not None:
        _write_json(project_dir / "paragraphs.json", chapter_paragraphs)
    if style_source is not None:
        _write_json(project_dir / "style_source.json", style_source)
    if scene_plan is not None:
        _write_json(project_dir / "scene_plan.json", scene_plan)
    if script_internal is not None:
        _write_json(project_dir / "script_internal.json", script_internal)
    if script_ui is not None:
        _write_json(project_dir / "script_ui.json", script_ui)
    if yaml_preview is not None:
        _write_json(project_dir / "yaml_preview.json", yaml_preview)
    if evidence_map:
        _write_json(project_dir / "evidence.json", evidence_map)
    if conversations:
        _write_json(project_dir / "conversations.json", conversations)
    if runs:
        _write_json(project_dir / "runs.json", runs)
    if exports:
        _write_json(project_dir / "exports.json", exports)

    return project_dir


def load_project(project_dir: Path) -> dict[str, Any]:
    """从本地目录加载单个项目的全部数据。"""
    data: dict[str, Any] = {
        "project": _read_json(project_dir / "project.json"),
        "chapters": _read_json(project_dir / "chapters.json"),
        "paragraphs": _read_json(project_dir / "paragraphs.json"),
        "style_source": _read_json(project_dir / "style_source.json"),
        "scene_plan": _read_json(project_dir / "scene_plan.json"),
        "script_internal": _read_json(project_dir / "script_internal.json"),
        "script_ui": _read_json(project_dir / "script_ui.json"),
        "yaml_preview": _read_json(project_dir / "yaml_preview.json"),
        "evidence": _read_json(project_dir / "evidence.json") or {},
        "conversations": _read_json(project_dir / "conversations.json") or [],
        "runs": _read_json(project_dir / "runs.json") or {},
        "exports": _read_json(project_dir / "exports.json") or {},
    }
    return data


def discover_projects(data_root: str) -> list[Path]:
    """扫描 data/ 目录，返回所有项目目录。"""
    root = Path(data_root)
    if not root.is_dir():
        return []
    return sorted(
        [entry for entry in root.iterdir() if entry.is_dir()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def delete_project_dir(data_root: str, project_name: str, project_id: str) -> None:
    """删除项目的本地数据目录。"""
    import shutil
    project_dir = project_data_dir(data_root, project_name, project_id)
    if project_dir.is_dir():
        shutil.rmtree(project_dir)
