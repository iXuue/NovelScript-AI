from app.services.validation_service import validate_traceability


def test_every_content_block_has_traceability_mapping():
    script = {
        "scenes": [{"scene_id": "S001", "content_blocks": [{"content_block_id": "CB001", "text": "她回来了。"}]}]
    }
    traceability = {
        "mappings": [{"content_block_id": "CB001", "scene_id": "S001", "source_evidence_id": "EV001"}]
    }
    result = validate_traceability(script, traceability)
    assert result.valid is True

