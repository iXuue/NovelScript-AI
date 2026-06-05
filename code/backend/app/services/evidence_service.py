from app.services.store import STORE


def get_evidence_by_content_block(content_block_id: str) -> dict:
    return STORE.evidence_by_content_block.get(content_block_id, {"content_block_id": content_block_id, "evidence": []})

