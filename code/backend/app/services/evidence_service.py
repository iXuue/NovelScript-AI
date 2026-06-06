from app.domain.artifacts import ArtifactStatus
from app.models.analysis import EvidenceItem
from app.models.chapter import Paragraph
from app.models.script import ScriptContentBlock, ScriptVersion
from app.services.store import STORE


def get_evidence_by_content_block(content_block_id: str, project_id: str | None = None, db=None) -> dict:
    if db is not None and project_id is not None:
        version = (
            db.query(ScriptVersion)
            .filter(
                ScriptVersion.project_id == project_id,
                ScriptVersion.status == ArtifactStatus.current,
                ScriptVersion.is_current.is_(True),
            )
            .one_or_none()
        )
        if version is None:
            version = (
                db.query(ScriptVersion)
                .filter(ScriptVersion.project_id == project_id)
                .order_by(ScriptVersion.generated_at.desc())
                .first()
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
        if block is None:
            return {"content_block_id": content_block_id, "evidence": []}
        if block.source_paragraph_ids:
            paragraphs = (
                db.query(Paragraph)
                .filter(Paragraph.project_id == project_id, Paragraph.paragraph_id.in_(block.source_paragraph_ids))
                .order_by(Paragraph.chapter_id, Paragraph.order)
                .all()
            )
            return {
                "content_block_id": content_block_id,
                "evidence": [
                    {
                        "source_paragraph_id": paragraph.paragraph_id,
                        "source_evidence_id": None,
                        "chapter_id": paragraph.chapter_id,
                        "paragraph_id": paragraph.paragraph_id,
                        "text": paragraph.text,
                    }
                    for paragraph in paragraphs
                ],
            }
        evidence_items = (
            db.query(EvidenceItem)
            .filter(EvidenceItem.project_id == project_id, EvidenceItem.evidence_id.in_(block.source_evidence_ids))
            .order_by(EvidenceItem.evidence_id)
            .all()
        )
        return {
            "content_block_id": content_block_id,
            "evidence": [
                {
                    "source_evidence_id": item.evidence_id,
                    "source_paragraph_id": None,
                    "chapter_id": item.chapter_id,
                    "paragraph_id": item.paragraph_id,
                    "text": item.quote,
                }
                for item in evidence_items
            ],
        }

    return STORE.evidence_by_content_block.get(content_block_id, {"content_block_id": content_block_id, "evidence": []})
