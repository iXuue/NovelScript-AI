def invalidate_after_style_change(scene_plan_confirmed: bool) -> list[str]:
    if scene_plan_confirmed:
        return []
    return ["style_profile", "scene_plan", "script_json"]


def invalidate_after_scene_plan_change() -> list[str]:
    return ["script_json", "traceability_index", "yaml_preview", "exports"]


def mark_downstream_stale(db, upstream_artifact_id: str) -> list[str]:
    return []

