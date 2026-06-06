from app.services.orchestrator_service import build_initial_generation_plan


def test_initial_generation_order():
    plan = build_initial_generation_plan()
    assert set(plan.parallel_groups[0]) == {"chapter_summary", "style_profile"}
    assert plan.dependencies["scene_plan"] == ["chapter_summary", "style_profile"]
