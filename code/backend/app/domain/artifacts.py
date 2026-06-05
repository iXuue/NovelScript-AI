from enum import StrEnum


class ArtifactStatus(StrEnum):
    current = "current"
    stale = "stale"
    historical = "historical"
    failed = "failed"


class ProjectStage(StrEnum):
    empty = "empty"
    uploaded = "uploaded"
    chapters_pending = "chapters_pending"
    chapters_confirmed = "chapters_confirmed"
    style_selected = "style_selected"
    scene_plan_draft = "scene_plan_draft"
    scene_plan_confirmed = "scene_plan_confirmed"
    script_generating = "script_generating"
    script_ready = "script_ready"
    failed = "failed"

