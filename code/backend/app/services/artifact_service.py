def invalidate_after_style_change(scene_plan_confirmed: bool) -> list[str]:
    if scene_plan_confirmed:
        return []
    return ["style_profile", "scene_plan", "script_json"]


def invalidate_after_scene_plan_change() -> list[str]:
    return ["script_json", "traceability_index", "yaml_preview", "exports"]


def mark_downstream_stale(db, upstream_artifact_id: str) -> list[str]:
    if db is None:
        return []
    if upstream_artifact_id.startswith("style_source:"):
        return mark_project_artifacts_stale(
            db,
            upstream_artifact_id.split(":", 1)[1],
            "style_source_changed",
            include_scene_plan=True,
            include_script=True,
            include_exports=True,
        )
    if upstream_artifact_id.startswith("scene_plan:"):
        return mark_project_artifacts_stale(
            db,
            upstream_artifact_id.split(":", 1)[1],
            "scene_plan_changed",
            include_scene_plan=False,
            include_script=True,
            include_exports=True,
        )
    return []


def mark_project_artifacts_stale(
    db,
    project_id: str,
    reason: str,
    *,
    include_scene_plan: bool,
    include_script: bool,
    include_exports: bool,
) -> list[str]:
    from app.domain.artifacts import ArtifactStatus
    from app.models.export import ExportJob
    from app.models.scene_plan import ScenePlan
    from app.models.script import ScriptVersion
    from app.services.store import now_utc

    changed: list[str] = []
    timestamp = now_utc()
    if include_scene_plan:
        for plan in db.query(ScenePlan).filter(ScenePlan.project_id == project_id, ScenePlan.is_current.is_(True)).all():
            plan.status = ArtifactStatus.stale
            plan.is_current = False
            plan.stale_reason = reason
            plan.updated_at = timestamp
            changed.append("scene_plan")
    if include_script:
        for script in db.query(ScriptVersion).filter(ScriptVersion.project_id == project_id, ScriptVersion.is_current.is_(True)).all():
            script.status = ArtifactStatus.stale
            script.is_current = False
            script.stale_reason = reason
            script.updated_at = timestamp
            changed.append("script_json")
    if include_exports:
        for export in db.query(ExportJob).filter(ExportJob.project_id == project_id, ExportJob.status == "succeeded").all():
            export.status = "stale"
            changed.append("exports")
    if changed:
        db.commit()
    return changed
