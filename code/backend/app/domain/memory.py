from pydantic import BaseModel, Field


class PromptMemory(BaseModel):
    stage: str
    scope: dict = Field(default_factory=dict)
    layers: dict = Field(default_factory=dict)
    compression_used: bool = False
    raw_full_novel_included: bool = False

