import pytest
from pydantic import ValidationError

from app.domain.scripts import ContentBlock, UserCleanScript
from app.domain.traceability import TraceabilityIndex


def test_internal_content_block_requires_content_block_id():
    block = ContentBlock(content_block_id="CB001", type="dialogue", speaker="林雨", text="我回来了。")
    assert block.content_block_id == "CB001"


def test_user_clean_script_rejects_internal_trace_fields():
    with pytest.raises(ValidationError):
        UserCleanScript(
            title="雨夜归来",
            characters=[],
            scenes=[],
            content_block_id="CB001",
        )


def test_traceability_maps_content_block_to_evidence():
    index = TraceabilityIndex(
        mappings=[
            {
                "content_block_id": "CB001",
                "scene_id": "S001",
                "source_evidence_id": "EV001",
                "chapter_id": "CH001",
                "paragraph_id": "CH001_P001",
            }
        ]
    )
    assert index.mappings[0].content_block_id == "CB001"

