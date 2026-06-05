from enum import StrEnum

from pydantic import BaseModel, Field


class RunStatus(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    budget_exceeded = "budget_exceeded"


class RunStepType(StrEnum):
    input_conversion = "input_conversion"
    chapter_detection = "chapter_detection"
    paragraph_numbering = "paragraph_numbering"
    chapter_summary = "chapter_summary"
    evidence_extraction = "evidence_extraction"
    story_bible = "story_bible"
    style_profile = "style_profile"
    scene_plan = "scene_plan"
    script_generation = "script_generation"
    validation = "validation"
    repair = "repair"
    export = "export"


class RunStepProgress(BaseModel):
    run_step_id: str
    step_type: str
    status: RunStatus
    summary: str


class AgentProgress(BaseModel):
    run_id: str
    status: RunStatus
    stage: str
    current_step: str | None = None
    steps: list[RunStepProgress] = Field(default_factory=list)
    failure_message: str | None = None

