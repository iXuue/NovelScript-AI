from pydantic import BaseModel


class EvidenceItem(BaseModel):
    source_evidence_id: str | None = None
    source_paragraph_id: str | None = None
    chapter_id: str
    paragraph_id: str
    text: str


class EvidenceLookupResult(BaseModel):
    content_block_id: str
    evidence: list[EvidenceItem]
