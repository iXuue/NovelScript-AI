from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.analysis import ChapterSummary, EvidenceItem
from app.models.chapter import Chapter, Paragraph
from app.models.checkpoint import Checkpoint
from app.models.export import ExportJob
from app.models.project import Project
from app.models.scene_plan import ScenePlan
from app.models.script import ScriptVersion
from app.models.story import StoryBible
from app.models.style import StyleProfile, StyleReferenceFile, StyleSourceRecord
from app.services.export_service import to_yaml_preview
from app.services.local_store import project_data_dir
from app.services.script_service import get_current_internal_script, get_current_script_for_ui, get_current_yaml_preview
from app.services.store import STORE

logger = logging.getLogger("novelscript")


def snapshot_enabled() -> bool:
    settings = get_settings()
    return settings.use_local_storage or settings.local_developer_logs_enabled


def snapshot_data_root() -> Path:
    root = Path(get_settings().local_data_root)
    if root.is_absolute():
        return root
    return Path(__file__).resolve().parents[2] / root


def save_project_snapshot_from_pg(db: Session | None, project_id: str, data_root: str | Path | None = None) -> Path | None:
    if db is None:
        return None
    project = db.get(Project, project_id)
    if project is None:
        return None

    root = Path(data_root) if data_root is not None else snapshot_data_root()
    project_dir = project_data_dir(str(root), project.name, project.project_id)
    project_dir.mkdir(parents=True, exist_ok=True)

    _write_json(project_dir / "project.json", _project_to_dict(project))
    _write_json(project_dir / "chapters.json", _chapters_to_dict(db, project_id))
    _write_json(project_dir / "paragraphs.json", _paragraphs_to_dict(db, project_id))
    _write_json(project_dir / "chapter_summaries.json", _chapter_summaries_to_dict(db, project_id))
    _write_json(project_dir / "evidence_items.json", _evidence_items_to_dict(db, project_id))
    _write_json(project_dir / "style_source.json", _style_source_to_dict(db, project_id))
    _write_json(project_dir / "style_reference_files.json", _style_reference_files_to_dict(db, project_id))
    _write_json(project_dir / "style_profile.json", _style_profile_to_dict(db, project_id))
    _write_json(project_dir / "story_bible.json", _story_bible_to_dict(db, project_id))
    _write_json(project_dir / "scene_plan.json", _scene_plan_to_dict(db, project_id))
    _write_json(project_dir / "script_internal.json", _script_internal_to_dict(db, project_id))
    _write_json(project_dir / "script_ui.json", get_current_script_for_ui(db, project_id))
    _write_json(project_dir / "yaml_preview.json", _yaml_preview_to_dict(db, project_id))
    _write_json(project_dir / "checkpoints.json", _checkpoints_to_dict(db, project_id))
    _write_json(project_dir / "exports.json", _exports_to_dict(db, project_id))
    _write_json(project_dir / "runs.json", _runs_to_dict(project_id))
    _write_json(project_dir / "conversations.json", STORE.conversations.get(project_id, []))
    _write_json(project_dir / "evidence_by_content_block.json", STORE.evidence_by_content_block)
    return project_dir


def mirror_project_snapshot(db: Session | None, project_id: str) -> None:
    if not snapshot_enabled():
        return
    try:
        save_project_snapshot_from_pg(db, project_id)
    except Exception:
        logger.exception("Failed to mirror project snapshot: %s", project_id)
        if db is not None:
            db.rollback()


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, default=_json_default)
    os.replace(tmp, path)


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _project_to_dict(project: Project) -> dict:
    return {
        "project_id": project.project_id,
        "name": project.name,
        "stage": project.stage,
        "primary_conversation_id": project.primary_conversation_id,
        "active_session_id": project.active_session_id,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }


def _chapters_to_dict(db: Session, project_id: str) -> list[dict]:
    chapters = db.query(Chapter).filter(Chapter.project_id == project_id).order_by(Chapter.order).all()
    return [
        {
            "chapter_id": chapter.chapter_id,
            "title": chapter.title,
            "order": chapter.order,
            "raw_text": chapter.raw_text,
            "paragraph_count": chapter.paragraph_count,
            "status": chapter.status,
            "created_at": chapter.created_at,
            "updated_at": chapter.updated_at,
        }
        for chapter in chapters
    ]


def _paragraphs_to_dict(db: Session, project_id: str) -> list[dict]:
    chapters = db.query(Chapter).filter(Chapter.project_id == project_id).order_by(Chapter.order).all()
    rows = []
    for chapter in chapters:
        paragraphs = (
            db.query(Paragraph)
            .filter(Paragraph.project_id == project_id, Paragraph.chapter_id == chapter.chapter_id)
            .order_by(Paragraph.order)
            .all()
        )
        rows.append(
            {
                "chapter_id": chapter.chapter_id,
                "paragraphs": [
                    {
                        "paragraph_id": paragraph.paragraph_id,
                        "order": paragraph.order,
                        "text": paragraph.text,
                        "created_at": paragraph.created_at,
                    }
                    for paragraph in paragraphs
                ],
            }
        )
    return rows


def _chapter_summaries_to_dict(db: Session, project_id: str) -> list[dict]:
    summaries = (
        db.query(ChapterSummary).filter(ChapterSummary.project_id == project_id).order_by(ChapterSummary.chapter_id).all()
    )
    return [
        {
            "chapter_id": summary.chapter_id,
            "title": summary.title,
            "summary": summary.summary,
            "key_events": summary.key_events,
            "characters": summary.characters,
            "locations": summary.locations,
            "conflicts": summary.conflicts,
            "foreshadowing": summary.foreshadowing,
            "adaptation_suggestions": summary.adaptation_suggestions,
            "source": summary.source,
            "created_at": summary.created_at,
            "updated_at": summary.updated_at,
        }
        for summary in summaries
    ]


def _evidence_items_to_dict(db: Session, project_id: str) -> list[dict]:
    items = db.query(EvidenceItem).filter(EvidenceItem.project_id == project_id).order_by(EvidenceItem.evidence_id).all()
    return [
        {
            "evidence_id": item.evidence_id,
            "chapter_id": item.chapter_id,
            "paragraph_ids": item.paragraph_ids or ([item.paragraph_id] if item.paragraph_id else []),
            "quote": item.quote,
            "evidence_type": item.evidence_type,
            "explanation": item.explanation,
            "related_characters": item.related_characters,
            "related_locations": item.related_locations,
            "related_plot_points": item.related_plot_points,
            "importance": item.importance,
            "must_keep": item.must_keep,
            "source": item.source,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }
        for item in items
    ]


def _style_source_to_dict(db: Session, project_id: str) -> dict | None:
    source = db.get(StyleSourceRecord, project_id)
    if source is None:
        return None
    payload = {"kind": source.kind}
    if source.kind == "builtin":
        payload["builtin_style"] = source.builtin_style
    elif source.kind == "custom_text":
        payload["style_text"] = source.style_text
    else:
        payload["reference_file_ids"] = source.reference_file_ids
    payload["created_at"] = source.created_at
    payload["updated_at"] = source.updated_at
    return payload


def _style_reference_files_to_dict(db: Session, project_id: str) -> list[dict]:
    files = db.query(StyleReferenceFile).filter(StyleReferenceFile.project_id == project_id).order_by(StyleReferenceFile.file_id).all()
    return [
        {
            "file_id": file.file_id,
            "filename": file.filename,
            "markdown": file.markdown,
            "created_at": file.created_at,
        }
        for file in files
    ]


def _style_profile_to_dict(db: Session, project_id: str) -> dict | None:
    profile = db.query(StyleProfile).filter(StyleProfile.project_id == project_id).order_by(StyleProfile.updated_at.desc()).first()
    if profile is None:
        return None
    return {
        "profile_text": profile.profile_text,
        "source": profile.source,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


def _story_bible_to_dict(db: Session, project_id: str) -> dict | None:
    bible = db.query(StoryBible).filter(StoryBible.project_id == project_id).order_by(StoryBible.updated_at.desc()).first()
    if bible is None:
        return None
    return {
        "title": bible.title,
        "story_type": bible.story_type,
        "tone": bible.tone,
        "logline": bible.logline,
        "theme": bible.theme,
        "main_characters": bible.main_characters,
        "relationships": bible.relationships,
        "locations": bible.locations,
        "timeline": bible.timeline,
        "central_conflict": bible.central_conflict,
        "foreshadowing": bible.foreshadowing,
        "source": bible.source,
        "created_at": bible.created_at,
        "updated_at": bible.updated_at,
    }


def _scene_plan_to_dict(db: Session, project_id: str) -> dict | None:
    scene_plan = (
        db.query(ScenePlan)
        .filter(ScenePlan.project_id == project_id)
        .order_by(ScenePlan.updated_at.desc())
        .first()
    )
    if scene_plan is None:
        return None
    validation = sorted(scene_plan.validations, key=lambda item: item.created_at, reverse=True)
    return {
        "scene_plan_id": scene_plan.scene_plan_id,
        "status": scene_plan.status,
        "confirmed": scene_plan.confirmed,
        "validation": _scene_plan_validation_to_dict(validation[0]) if validation else None,
        "source": scene_plan.source,
        "created_at": scene_plan.created_at,
        "updated_at": scene_plan.updated_at,
        "scenes": [
            {
                "scene_id": scene.scene_id,
                "order": scene.order,
                "title": scene.title,
                "source_chapter_ids": scene.source_chapter_ids,
                "source_evidence_ids": scene.source_evidence_ids,
                "source_paragraph_ids": scene.source_paragraph_ids,
                "interior_exterior": scene.interior_exterior,
                "location": scene.location,
                "time": scene.time,
                "characters": scene.characters,
                "must_cover_plot": scene.must_cover_plot,
                "must_keep_dialogue": scene.must_keep_dialogue,
                "must_keep_visual_elements": scene.must_keep_visual_elements,
                "must_keep_foreshadowing": scene.must_keep_foreshadowing,
                "scene_function": scene.scene_function,
                "core_conflict": scene.core_conflict,
                "adaptation_note": scene.adaptation_note,
                "created_at": scene.created_at,
                "updated_at": scene.updated_at,
            }
            for scene in sorted(scene_plan.scenes, key=lambda item: item.order)
        ],
    }


def _scene_plan_validation_to_dict(validation) -> dict:
    return {
        "passed": validation.passed,
        "issues": validation.issues,
        "suggestions": validation.suggestions,
        "coverage": validation.coverage,
        "source": validation.source,
        "created_at": validation.created_at,
        "updated_at": validation.updated_at,
    }


def _script_internal_to_dict(db: Session, project_id: str) -> dict | None:
    current = get_current_internal_script(db, project_id)
    if current is None:
        return None
    return current[1]


def _yaml_preview_to_dict(db: Session, project_id: str) -> dict | None:
    preview = get_current_yaml_preview(db, project_id)
    if preview is not None:
        return preview
    internal = _script_internal_to_dict(db, project_id)
    if internal is None:
        return None
    version = (
        db.query(ScriptVersion)
        .filter(ScriptVersion.project_id == project_id)
        .order_by(ScriptVersion.generated_at.desc())
        .first()
    )
    return {
        "script_version_id": version.script_version_id if version else None,
        "status": version.status if version else None,
        "yaml": to_yaml_preview(internal),
        "generated_at": version.generated_at if version else None,
    }


def _checkpoints_to_dict(db: Session, project_id: str) -> list[dict]:
    checkpoints = db.query(Checkpoint).filter(Checkpoint.project_id == project_id).order_by(Checkpoint.created_at).all()
    return [
        {
            "checkpoint_id": checkpoint.checkpoint_id,
            "stage": checkpoint.stage,
            "created_at": checkpoint.created_at,
        }
        for checkpoint in checkpoints
    ]


def _exports_to_dict(db: Session, project_id: str) -> list[dict]:
    exports = db.query(ExportJob).filter(ExportJob.project_id == project_id).order_by(ExportJob.created_at).all()
    return [
        {
            "export_id": export.export_id,
            "script_version_id": export.script_version_id,
            "format": export.format,
            "status": export.status,
            "filename": export.filename,
            "content_type": export.content_type,
            "file_path": export.file_path,
            "created_at": export.created_at,
        }
        for export in exports
    ]


def _runs_to_dict(project_id: str) -> dict:
    return {run_id: run for run_id, run in STORE.runs.items() if run.get("project_id") == project_id}
