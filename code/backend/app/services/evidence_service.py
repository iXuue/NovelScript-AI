from app.services.store import STORE
from app.domain.artifacts import ArtifactStatus
from app.models.analysis import EvidenceItem
from app.models.script import ScriptContentBlock, ScriptVersion


def get_evidence_by_content_block(project_id: str, content_block_id: str, db=None) -> dict:
    if db is None:
        return STORE.evidence_by_content_block.get(content_block_id, {"content_block_id": content_block_id, "evidence": []})

    version = (
        db.query(ScriptVersion)
        .filter(ScriptVersion.project_id == project_id, ScriptVersion.status == ArtifactStatus.current)
        .one_or_none()
    )
    if version is None:
        return {"content_block_id": content_block_id, "evidence": []}

    block = (
        db.query(ScriptContentBlock)
        .filter(
            ScriptContentBlock.project_id == project_id,
            ScriptContentBlock.script_version_id == version.script_version_id,
            ScriptContentBlock.content_block_id == content_block_id,
        )
        .one_or_none()
    )
    if block is None or not block.source_evidence_ids:
        return {"content_block_id": content_block_id, "evidence": []}

    evidence_rows = (
        db.query(EvidenceItem)
        .filter(EvidenceItem.project_id == project_id, EvidenceItem.evidence_id.in_(block.source_evidence_ids))
        .all()
    )
    evidence_by_id = {item.evidence_id: item for item in evidence_rows}
    return {
        "content_block_id": content_block_id,
        "evidence": [
            {
                "source_evidence_id": evidence.evidence_id,
                "chapter_id": evidence.chapter_id,
                "paragraph_id": evidence.paragraph_id,
                "text": evidence.quote,
            }
            for evidence_id in block.source_evidence_ids
            if (evidence := evidence_by_id.get(evidence_id)) is not None
        ],
    }
