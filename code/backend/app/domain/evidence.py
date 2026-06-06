from pydantic import BaseModel


class EvidenceItem(BaseModel):
    source_evidence_id: str
    chapter_id: str
    paragraph_ids: list[str]
    text: str


class EvidenceLookupResult(BaseModel):
    content_block_id: str
    evidence: list[EvidenceItem]

