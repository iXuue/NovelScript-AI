from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app.domain.artifacts import ArtifactStatus
from app.models.feedback_plan_cache import FeedbackPlanCacheEntry
from app.models.scene_plan import ScenePlan
from app.models.script import ScriptVersion
from app.services.store import now_utc, persistent_id


VALID_TARGET_TYPES = {"scene_plan", "script", "chapter", "scene"}


def normalize_feedback_text(text: str) -> str:
    return " ".join(text.strip().split()).casefold()


def feedback_input_hash(text: str) -> str:
    return hashlib.sha256(normalize_feedback_text(text).encode("utf-8")).hexdigest()


def normalize_target(target: dict[str, Any]) -> dict[str, Any]:
    target_type = str(target.get("type") or "").strip()
    if target_type not in VALID_TARGET_TYPES:
        raise ValueError(f"unsupported feedback target type: {target_type}")
    normalized: dict[str, Any] = {"type": target_type}
    if target_type == "scene":
        scene_id = str(target.get("scene_id") or "").strip()
        if not scene_id:
            raise ValueError("scene feedback target requires scene_id")
        normalized["scene_id"] = scene_id
    if target_type == "chapter":
        chapter_id = str(target.get("chapter_id") or "").strip()
        if not chapter_id:
            raise ValueError("chapter feedback target requires chapter_id")
        normalized["chapter_id"] = chapter_id
    return normalized


def stage_for_target(target: dict[str, Any]) -> str:
    return "scene_plan" if target["type"] == "scene_plan" else "script"


def scope_id_for_target(target: dict[str, Any]) -> str:
    target_type = target["type"]
    if target_type == "scene":
        return target["scene_id"]
    if target_type == "chapter":
        return target["chapter_id"]
    return target_type


def current_artifact_fingerprint(db: Session, project_id: str, stage: str) -> str:
    if stage == "scene_plan":
        scene_plan = (
            db.query(ScenePlan)
            .filter(ScenePlan.project_id == project_id, ScenePlan.is_current.is_(True), ScenePlan.status == ArtifactStatus.current)
            .order_by(ScenePlan.version_number.desc())
            .first()
        )
        if scene_plan is None:
            return "scene_plan:none"
        updated_at = scene_plan.updated_at.isoformat() if scene_plan.updated_at else ""
        return f"scene_plan:{scene_plan.scene_plan_id}:{scene_plan.version_number}:{updated_at}:{scene_plan.confirmed}"

    script_version = (
        db.query(ScriptVersion)
        .filter(ScriptVersion.project_id == project_id, ScriptVersion.is_current.is_(True), ScriptVersion.status == ArtifactStatus.current)
        .order_by(ScriptVersion.version_number.desc())
        .first()
    )
    if script_version is not None:
        updated_at = script_version.updated_at.isoformat() if script_version.updated_at else ""
        return f"script:{script_version.script_version_id}:{script_version.version_number}:{updated_at}"

    scene_plan = (
        db.query(ScenePlan)
        .filter(ScenePlan.project_id == project_id, ScenePlan.is_current.is_(True), ScenePlan.status == ArtifactStatus.current)
        .order_by(ScenePlan.version_number.desc())
        .first()
    )
    if scene_plan is not None:
        updated_at = scene_plan.updated_at.isoformat() if scene_plan.updated_at else ""
        return f"confirmed_scene_plan:{scene_plan.scene_plan_id}:{scene_plan.version_number}:{updated_at}:{scene_plan.confirmed}"
    return "script:none"


def find_cached_feedback_plan(
    db: Session,
    *,
    project_id: str,
    stage: str,
    target: dict[str, Any],
    user_feedback: str,
    artifact_fingerprint: str,
) -> FeedbackPlanCacheEntry | None:
    return (
        db.query(FeedbackPlanCacheEntry)
        .filter(
            FeedbackPlanCacheEntry.project_id == project_id,
            FeedbackPlanCacheEntry.stage == stage,
            FeedbackPlanCacheEntry.target_type == target["type"],
            FeedbackPlanCacheEntry.scope_id == scope_id_for_target(target),
            FeedbackPlanCacheEntry.input_hash == feedback_input_hash(user_feedback),
            FeedbackPlanCacheEntry.artifact_fingerprint == artifact_fingerprint,
        )
        .order_by(FeedbackPlanCacheEntry.created_at.desc())
        .first()
    )


def store_feedback_plan(
    db: Session,
    *,
    project_id: str,
    message_id: str | None,
    stage: str,
    target: dict[str, Any],
    user_feedback: str,
    artifact_fingerprint: str,
    modification_plan: dict[str, Any],
    source_requests: list[dict[str, Any]],
) -> FeedbackPlanCacheEntry:
    timestamp = now_utc()
    entry = FeedbackPlanCacheEntry(
        feedback_plan_id=persistent_id("fbp"),
        project_id=project_id,
        message_id=message_id,
        stage=stage,
        target_type=target["type"],
        scope_id=scope_id_for_target(target),
        input_hash=feedback_input_hash(user_feedback),
        artifact_fingerprint=artifact_fingerprint,
        user_feedback=user_feedback,
        target=target,
        modification_plan=modification_plan,
        source_requests=source_requests,
        cache_hit=False,
        created_at=timestamp,
        updated_at=timestamp,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_feedback_plan(db: Session, project_id: str, feedback_plan_id: str) -> FeedbackPlanCacheEntry:
    entry = db.get(FeedbackPlanCacheEntry, feedback_plan_id)
    if entry is None or entry.project_id != project_id:
        raise KeyError("feedback_plan_not_found")
    return entry


def feedback_plan_to_dict(entry: FeedbackPlanCacheEntry, *, cache_hit: bool = False) -> dict[str, Any]:
    return {
        "feedback_plan_id": entry.feedback_plan_id,
        "message_id": entry.message_id,
        "stage": entry.stage,
        "target": entry.target,
        "target_type": entry.target_type,
        "scope_id": entry.scope_id,
        "artifact_fingerprint": entry.artifact_fingerprint,
        "user_feedback": entry.user_feedback,
        "modification_plan": entry.modification_plan,
        "source_requests": entry.source_requests,
        "cache_hit": cache_hit,
        "created_at": entry.created_at,
        "updated_at": entry.updated_at,
    }


def stable_json_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()
