from app.services.orchestrator_service import build_initial_generation_plan


def test_initial_generation_order():
    plan = build_initial_generation_plan()
    assert set(plan.parallel_groups[0]) == {"chapter_summary", "evidence_extraction", "style_profile"}
    assert plan.dependencies["story_bible"] == ["chapter_summary", "evidence_extraction"]
    assert plan.dependencies["scene_plan"] == ["story_bible", "style_profile"]

