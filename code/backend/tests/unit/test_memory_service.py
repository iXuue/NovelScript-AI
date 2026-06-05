from app.services.memory_service import build_prompt_memory


def test_long_context_uses_summary_without_raw_truncation():
    memory = build_prompt_memory(
        stage="script_generation",
        scope={"scene_id": "S001"},
        chapter_summaries=[{"chapter_id": "CH001", "summary": "女主雨夜回到旧宅。"}],
        evidence_refs=[{"source_evidence_id": "EV001", "paragraph_id": "CH001_P001"}],
        story_bible={"characters": [{"name": "林雨"}]},
        style_profile={"dialogue": "短句，压迫感强"},
        conversation_summary="用户要求节奏更紧张。",
        raw_context_characters=80000,
        max_prompt_characters=12000,
    )

    assert memory.compression_used is True
    assert "chapter_summaries" in memory.layers
    assert "story_bible" in memory.layers
    assert "style_profile" in memory.layers
    assert "conversation_summary" in memory.layers
    assert memory.raw_full_novel_included is False


def test_scene_edit_memory_uses_confirmed_scene_plan_and_scene_evidence():
    memory = build_prompt_memory(
        stage="conversation_edit",
        scope={"scene_id": "S001"},
        confirmed_scene_plan={"scene_id": "S001", "title": "雨夜归来"},
        scene_evidence_refs=[{"source_evidence_id": "EV001", "paragraph_id": "CH001_P001"}],
        conversation_summary="用户要求第一场对白更短。",
        max_prompt_characters=6000,
    )

    assert "confirmed_scene_plan" in memory.layers
    assert "scene_evidence_refs" in memory.layers
    assert memory.scope["scene_id"] == "S001"

