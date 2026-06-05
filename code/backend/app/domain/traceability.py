from pydantic import BaseModel


class TraceabilityMapping(BaseModel):
    content_block_id: str
    scene_id: str
    source_evidence_id: str
    chapter_id: str | None = None
    paragraph_id: str | None = None


class TraceabilityIndex(BaseModel):
    mappings: list[TraceabilityMapping]

