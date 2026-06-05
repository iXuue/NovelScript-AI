from pydantic import BaseModel, ConfigDict, Field


class ContentBlock(BaseModel):
    content_block_id: str
    type: str
    text: str
    speaker: str | None = None
    source_evidence_ids: list[str] = Field(default_factory=list)


class InternalScriptScene(BaseModel):
    scene_id: str
    title: str
    source_chapter_ids: list[str] = Field(default_factory=list)
    content_blocks: list[ContentBlock] = Field(default_factory=list)


class InternalScript(BaseModel):
    title: str
    characters: list[dict] = Field(default_factory=list)
    scenes: list[InternalScriptScene] = Field(default_factory=list)


class UserCleanScript(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    characters: list[dict]
    scenes: list[dict]

